"""Tests for transcript attachment persistence.

The persistence path is tested via a pure-function helper
``build_transcript_attachment_envelope`` that takes resolved attachments
and produces both the JSON envelope written to ``transcript_entries``
and the side-effect of writing staged attachments to
``media/transcripts/<session>/<sha256>``.

The envelope MUST NOT use the field name ``file_uuid``; that is an
upload-store concept which would leak into the engine on replay. Staged
attachments use ``sha256_ref`` instead.

Deferred coverage: dedupe-within-session against an existing on-disk sha +
transcript-disk-budget fallback to inline-in-envelope. The current
implementation deduplicates implicitly (sha-keyed paths overwrite to the same
content); the explicit "fall back to inline when budget exceeded" test belongs
with the budget tracker.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from opensquilla.gateway.transcripts import (
    build_transcript_attachment_envelope,
    rebuild_attachments_for_replay,
)


def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


# ---------------------------------------------------------------------------
# Test 1 — regression: inline attachment shape preserved.
# ---------------------------------------------------------------------------

def test_inline_attachment_stored_in_transcript_envelope(tmp_path: Path) -> None:
    inline = {"type": "image/png", "data": _b64(b"\x89PNG\r\n\x1a\n"), "name": "p.png"}
    envelope, writes = build_transcript_attachment_envelope(
        text="hi",
        attachments=[inline],
        session_id="s1",
        media_root=tmp_path,
        persist_enabled=True,
    )
    parsed = json.loads(envelope)
    assert parsed["text"] == "hi"
    persisted = parsed["attachments"][0]
    assert persisted["type"] == "image/png"
    assert persisted["data"] == inline["data"]
    assert "sha256_ref" not in persisted
    assert writes == []


# ---------------------------------------------------------------------------
# Test 2 — staged attachment persisted to disk by sha256, envelope uses sha256_ref.
# ---------------------------------------------------------------------------

def test_staged_attachment_persisted_to_disk_and_referenced_by_sha256(
    tmp_path: Path,
) -> None:
    pdf = b"%PDF-1.4\nbody\n"
    sha = hashlib.sha256(pdf).hexdigest()
    staged = {
        "type": "application/pdf",
        "data": _b64(pdf),
        "name": "r.pdf",
        "_was_staged": True,
    }
    envelope, writes = build_transcript_attachment_envelope(
        text="summarise",
        attachments=[staged],
        session_id="s1",
        media_root=tmp_path,
        persist_enabled=True,
    )
    parsed = json.loads(envelope)
    persisted = parsed["attachments"][0]
    assert persisted["sha256_ref"] == sha
    assert persisted["name"] == "r.pdf"
    assert persisted["mime"] == "application/pdf"
    assert persisted["size"] == len(pdf)
    # NOT file_uuid; upload-store identifiers stay out of persisted transcript envelopes.
    assert "file_uuid" not in persisted
    assert "data" not in persisted

    # Disk write happened.
    expected_path = tmp_path / "transcripts" / "s1" / sha
    assert expected_path.exists()
    assert expected_path.read_bytes() == pdf
    assert any(Path(w["path"]) == expected_path for w in writes)


def test_transcript_envelope_uses_sha256_ref_not_file_uuid(tmp_path: Path) -> None:
    """Envelope field name is sha256_ref, never file_uuid."""

    pdf = b"%PDF-1.4\n"
    staged = {
        "type": "application/pdf",
        "data": _b64(pdf),
        "name": "r.pdf",
        "_was_staged": True,
    }
    envelope, _ = build_transcript_attachment_envelope(
        text="x",
        attachments=[staged],
        session_id="s",
        media_root=tmp_path,
        persist_enabled=True,
    )
    assert "file_uuid" not in envelope
    assert "sha256_ref" in envelope


# ---------------------------------------------------------------------------
# Test 3 — persist disabled keeps everything inline.
# ---------------------------------------------------------------------------

def test_persist_transcripts_disabled_skips_disk_copy(tmp_path: Path) -> None:
    pdf = b"%PDF-1.4\n"
    staged = {
        "type": "application/pdf",
        "data": _b64(pdf),
        "name": "r.pdf",
        "_was_staged": True,
    }
    envelope, writes = build_transcript_attachment_envelope(
        text="x",
        attachments=[staged],
        session_id="s1",
        media_root=tmp_path,
        persist_enabled=False,
    )
    parsed = json.loads(envelope)
    persisted = parsed["attachments"][0]
    assert persisted.get("data") == _b64(pdf)
    assert "sha256_ref" not in persisted
    assert writes == []


# ---------------------------------------------------------------------------
# Test 4 — dedupe by sha (free side effect of sha-keyed paths).
# ---------------------------------------------------------------------------

def test_transcript_dedup_within_session(tmp_path: Path) -> None:
    pdf = b"%PDF-1.4\nidentical\n"
    staged = {
        "type": "application/pdf",
        "data": _b64(pdf),
        "name": "r.pdf",
        "_was_staged": True,
    }
    build_transcript_attachment_envelope(
        text="first", attachments=[staged], session_id="s1",
        media_root=tmp_path, persist_enabled=True,
    )
    build_transcript_attachment_envelope(
        text="second", attachments=[staged], session_id="s1",
        media_root=tmp_path, persist_enabled=True,
    )
    sha = hashlib.sha256(pdf).hexdigest()
    files = list((tmp_path / "transcripts" / "s1").iterdir())
    assert [f.name for f in files] == [sha], files


# ---------------------------------------------------------------------------
# Test 5 — replay rebuilds from sha256_ref by reading the on-disk copy.
# ---------------------------------------------------------------------------

def test_replay_resolves_sha256_ref_without_file_uuid_in_engine(tmp_path: Path) -> None:
    """Engine never observes file_uuid — replay reads sha-keyed file."""

    pdf = b"%PDF-1.4\nbody\n"
    sha = hashlib.sha256(pdf).hexdigest()
    persist_dir = tmp_path / "transcripts" / "s1"
    persist_dir.mkdir(parents=True, exist_ok=True)
    (persist_dir / sha).write_bytes(pdf)

    envelope = json.dumps(
        {
            "text": "replay me",
            "attachments": [
                {
                    "sha256_ref": sha,
                    "name": "r.pdf",
                    "mime": "application/pdf",
                    "size": len(pdf),
                }
            ],
        }
    )
    text, attachments = rebuild_attachments_for_replay(
        envelope, session_id="s1", media_root=tmp_path
    )
    assert text == "replay me"
    assert len(attachments) == 1
    att = attachments[0]
    # No file_uuid leak.
    assert "file_uuid" not in att
    # Bytes are inlined for the engine.
    assert base64.b64decode(att["data"]) == pdf
    assert att["type"] == "application/pdf"


# ---------------------------------------------------------------------------
# Test 6 — replay degrades gracefully when the persisted file is missing.
# ---------------------------------------------------------------------------

def test_transcript_persistence_falls_back_to_inline_when_budget_exceeded(
    tmp_path: Path,
) -> None:
    """When disk_budget_bytes would be exceeded, the writer falls back to
    inline-in-envelope rather than crashing the persist.

    Counter ``transcript.disk.budget_exceeded`` increments and the envelope
    reverts to the existing ``{type, data, name}`` shape so the transcript still
    preserves the attachment.
    """
    pdf = b"%PDF-1.4\n" + b"a" * 50_000  # 50 KB
    staged = {
        "type": "application/pdf",
        "data": _b64(pdf),
        "name": "r.pdf",
        "_was_staged": True,
    }
    envelope, writes = build_transcript_attachment_envelope(
        text="x",
        attachments=[staged],
        session_id="s1",
        media_root=tmp_path,
        persist_enabled=True,
        disk_budget_bytes=10_000,  # cap below the payload size
    )
    parsed = json.loads(envelope)
    persisted = parsed["attachments"][0]
    # Fallback path: inline data, no sha256_ref, no on-disk write.
    assert persisted.get("data") == _b64(pdf)
    assert "sha256_ref" not in persisted
    assert writes == []
    transcripts_dir = tmp_path / "transcripts" / "s1"
    assert not transcripts_dir.exists() or not list(transcripts_dir.iterdir())


def test_replay_with_missing_persisted_file_degrades_gracefully(
    tmp_path: Path,
) -> None:
    sha = "a" * 64
    envelope = json.dumps(
        {
            "text": "replay me",
            "attachments": [
                {
                    "sha256_ref": sha,
                    "name": "missing.pdf",
                    "mime": "application/pdf",
                    "size": 12345,
                }
            ],
        }
    )
    text, attachments = rebuild_attachments_for_replay(
        envelope, session_id="s1", media_root=tmp_path
    )
    # No crash; attachments dropped; text carries a placeholder marker for
    # the missing one so the model is informed.
    assert "[attachment unavailable: missing.pdf]" in text
    assert attachments == []


def test_replay_missing_marker_sanitizes_attachment_name(tmp_path: Path) -> None:
    sha = "b" * 64
    envelope = json.dumps(
        {
            "text": "replay me",
            "attachments": [
                {
                    "sha256_ref": sha,
                    "name": "bad\nname.pdf",
                    "mime": "application/pdf",
                    "size": 12345,
                }
            ],
        }
    )

    text, attachments = rebuild_attachments_for_replay(
        envelope, session_id="s1", media_root=tmp_path
    )

    assert "[attachment unavailable: bad name.pdf]" in text
    assert attachments == []
