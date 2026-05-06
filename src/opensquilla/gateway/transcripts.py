"""Transcript attachment persistence + replay.

The gateway-side transcript writer used to inline the full base64 of
every attachment. Now, attachments that were originally **staged**
with ``file_uuid`` are written to a
content-addressable per-session directory instead — the envelope keeps
just ``{sha256_ref, name, mime, size}``. Inline attachments retain the
existing envelope shape so existing replay paths are unchanged.

The persisted envelope field is ``sha256_ref``, never ``file_uuid``:
``file_uuid`` is an upload-store concept that must not leak into engine
replay paths.

The on-disk byte budget is enforced at write time: when the next
write would exceed ``disk_budget_bytes``, the writer falls back to
inline-in-envelope and emits the ``transcript.disk.budget_exceeded``
warning instead of failing the persist. This avoids silent truncation
without silently filling disk.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Marker text for replay when the persisted file is missing on disk.
_MISSING_ATTACHMENT_TEMPLATE = "[attachment unavailable: {name}]"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write *data* to *path* atomically via tmp + fsync + os.replace.

    A unique temp file is written alongside the target, fsynced, then
    renamed over the target.  If any step fails the temp file is
    removed so no half-written residue is left behind.
    """
    tmp_path = Path(str(path) + f".tmp.{os.getpid()}.{secrets.token_hex(4)}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _display_attachment_name(raw: Any, fallback: str = "attachment") -> str:
    if not isinstance(raw, str):
        return fallback
    collapsed = " ".join(raw.strip().split())
    if not collapsed:
        return fallback
    return collapsed[:160]


def _was_staged(attachment: dict[str, Any]) -> bool:
    return bool(attachment.get("_was_staged"))


def _transcript_dir(media_root: Path, session_id: str) -> Path:
    return Path(media_root) / "transcripts" / session_id


def _media_disk_usage_bytes(media_root: Path) -> int:
    """Best-effort sum of ``media/transcripts/**`` byte usage."""

    root = Path(media_root) / "transcripts"
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def build_transcript_attachment_envelope(
    *,
    text: str,
    attachments: list[dict[str, Any]],
    session_id: str,
    media_root: Path,
    persist_enabled: bool,
    disk_budget_bytes: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Build the JSON envelope written to ``transcript_entries.content``.

    Returns ``(envelope_json, disk_writes)`` where ``disk_writes`` is a
    list of ``{"path", "sha256", "size"}`` dicts describing which staged
    attachments landed on disk (one per unique sha within this call).

    When ``disk_budget_bytes`` is provided and a write would push the
    transcript dir's total byte usage beyond it, the persistence falls
    back to inline-in-envelope for that attachment and a
    ``transcript.disk.budget_exceeded`` warning is logged. The on-disk
    path is left untouched in that case.
    """

    persisted_attachments: list[dict[str, Any]] = []
    disk_writes: list[dict[str, Any]] = []
    transcripts_dir: Path | None = None
    current_disk_bytes: int | None = (
        _media_disk_usage_bytes(media_root) if disk_budget_bytes is not None else None
    )

    for attachment in attachments:
        media_type = (
            attachment.get("type") or attachment.get("mime") or attachment.get("media_type")
        )
        name = attachment.get("name", "attachment")
        data = attachment.get("data")
        if not isinstance(data, str) or not isinstance(media_type, str):
            continue

        if persist_enabled and _was_staged(attachment):
            try:
                payload = base64.b64decode(data, validate=True)
            except (ValueError, TypeError) as exc:
                log.warning("transcript.persist_decode_failed name=%s err=%s", name, exc)
                # Fall through to inline copy if decode fails.
                persisted_attachments.append(
                    {"type": media_type, "name": name, "data": data}
                )
                continue

            sha = hashlib.sha256(payload).hexdigest()
            if transcripts_dir is None:
                transcripts_dir = _transcript_dir(media_root, session_id)
                transcripts_dir.mkdir(parents=True, exist_ok=True)
            path = transcripts_dir / sha
            already_on_disk = path.exists()
            if not already_on_disk:
                # Budget guard: if writing this payload would
                # push transcript dir beyond the budget, fall back to
                # inline-in-envelope rather than fail the persist.
                if (
                    disk_budget_bytes is not None
                    and current_disk_bytes is not None
                    and current_disk_bytes + len(payload) > disk_budget_bytes
                ):
                    log.warning(
                        "transcript.disk.budget_exceeded session=%s sha=%s "
                        "current=%d budget=%d size=%d — falling back to inline",
                        session_id,
                        sha,
                        current_disk_bytes,
                        disk_budget_bytes,
                        len(payload),
                    )
                    persisted_attachments.append(
                        {"type": media_type, "name": name, "data": data}
                    )
                    continue
                _atomic_write_bytes(path, payload)
                disk_writes.append({"path": str(path), "sha256": sha, "size": len(payload)})
                if current_disk_bytes is not None:
                    current_disk_bytes += len(payload)

            persisted_attachments.append(
                {
                    "sha256_ref": sha,
                    "name": name,
                    "mime": media_type,
                    "size": len(payload),
                }
            )
        else:
            persisted_attachments.append(
                {"type": media_type, "name": name, "data": data}
            )

    envelope = json.dumps({"text": text, "attachments": persisted_attachments})
    return envelope, disk_writes


def rebuild_attachments_for_replay(
    envelope_json: str,
    *,
    session_id: str,
    media_root: Path,
) -> tuple[str, list[dict[str, Any]]]:
    """Rebuild ``(text, attachments)`` for engine replay.

    For each ``sha256_ref`` envelope entry the function reads the bytes
    from ``media_root/transcripts/<session>/<sha>`` and re-inlines them
    as base64. A missing on-disk file degrades to a placeholder marker
    appended to ``text``; the attachment is dropped rather than crashing
    the engine.
    """

    try:
        parsed = json.loads(envelope_json)
    except (json.JSONDecodeError, ValueError):
        return envelope_json, []

    if not isinstance(parsed, dict):
        return envelope_json, []

    raw_text = parsed.get("text")
    text = raw_text if isinstance(raw_text, str) else ""
    raw_atts = parsed.get("attachments")
    if not isinstance(raw_atts, list):
        return text, []

    rebuilt: list[dict[str, Any]] = []
    missing_markers: list[str] = []
    transcripts_dir = _transcript_dir(media_root, session_id)

    for entry in raw_atts:
        if not isinstance(entry, dict):
            continue
        sha = entry.get("sha256_ref")
        if isinstance(sha, str) and sha:
            path = transcripts_dir / sha
            if not path.exists():
                missing_markers.append(
                    _MISSING_ATTACHMENT_TEMPLATE.format(
                        name=_display_attachment_name(entry.get("name"))
                    )
                )
                log.warning(
                    "transcript.replay.missing_attachment session=%s sha=%s name=%s",
                    session_id,
                    sha,
                    entry.get("name", "?"),
                )
                continue
            payload = path.read_bytes()
            raw_name = entry.get("name", "attachment")
            rebuilt.append(
                {
                    "type": entry.get("mime") or entry.get("type"),
                    "data": base64.b64encode(payload).decode("ascii"),
                    "name": raw_name if isinstance(raw_name, str) else "attachment",
                }
            )
        else:
            # Inline-shaped entry — pass through.
            data = entry.get("data")
            mime = entry.get("type") or entry.get("mime")
            if isinstance(data, str) and isinstance(mime, str):
                raw_name = entry.get("name", "attachment")
                rebuilt.append(
                    {
                        "type": mime,
                        "data": data,
                        "name": raw_name if isinstance(raw_name, str) else "attachment",
                    }
                )

    if missing_markers:
        text = "\n".join([text, *missing_markers]).strip()

    return text, rebuilt
