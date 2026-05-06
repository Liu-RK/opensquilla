"""Capability-gated channel status reactions."""

from __future__ import annotations

# fmt: off
# ruff: noqa: E501,E701,E702
from typing import Any, Protocol

from opensquilla.channels.types import IncomingMessage

SLACK_STATUS_EMOJI = {"received": "white_check_mark", "running": "eyes", "failed": "x"}
FEISHU_STATUS_EMOJI = {"received": "DONE", "running": "EYES", "failed": "X"}

class StatusReactor(Protocol):
    async def received(self, message: IncomingMessage) -> None: ...
    async def running(self, message: IncomingMessage) -> None: ...
    async def failed(self, message: IncomingMessage) -> None: ...
    async def completed(self, message: IncomingMessage) -> None: ...

class NullStatusReactor:
    async def received(self, message: IncomingMessage) -> None: return None
    running = failed = completed = received

class _BaseStatusReactor:
    def __init__(self, adapter: str, logger: Any) -> None:
        self._adapter = adapter; self._log = logger; self._disabled = False; self._active: list[Any] = []
    async def received(self, message: IncomingMessage) -> None: await self._add_state(message, "received")
    async def running(self, message: IncomingMessage) -> None: await self._add_state(message, "running")
    async def failed(self, message: IncomingMessage) -> None: await self._add_state(message, "failed")
    async def completed(self, message: IncomingMessage) -> None:
        for token in list(self._active):
            await self._remove(token); self._active.remove(token)
    async def _add_state(self, message: IncomingMessage, state: str) -> None:
        if not self._disabled and (token := await self._add(message, state)) is not None: self._active.append(token)
    async def _add(self, message: IncomingMessage, state: str) -> Any: raise NotImplementedError
    async def _remove(self, token: Any) -> None: raise NotImplementedError
    def _disable(self, reason: str) -> None:
        if not self._disabled:
            self._disabled = True; self._log.warning("channel.status_reaction_disabled", adapter=self._adapter, reason=reason)

class SlackStatusReactor(_BaseStatusReactor):
    def __init__(self, channel: Any, logger: Any) -> None:
        super().__init__("slack", logger); self._channel = channel
    async def _remove(self, payload: dict[str, str]) -> None: await self._post("/reactions.remove", payload)
    async def _add(self, message: IncomingMessage, state: str) -> dict[str, str] | None:
        ts = message.metadata.get("ts") or message.metadata.get("thread_ts")
        if not isinstance(ts, str) or not ts: return None
        payload = {"channel": message.channel_id, "timestamp": ts, "name": SLACK_STATUS_EMOJI[state]}
        return payload if await self._post("/reactions.add", payload) else None
    async def _post(self, path: str, payload: dict[str, str]) -> bool:
        resp = await self._channel._get_client().post(path, json=payload)
        if resp.status_code == 403: self._disable("missing_oauth_scope"); return False
        resp.raise_for_status(); data = resp.json()
        if data.get("ok"): return True
        if data.get("error") in {"missing_scope", "not_allowed_token_type"}: self._disable("missing_oauth_scope"); return False
        raise RuntimeError(f"Slack API error: {data.get('error')}")

class FeishuStatusReactor(_BaseStatusReactor):
    def __init__(self, channel: Any, logger: Any) -> None:
        super().__init__("feishu", logger); self._channel = channel
    async def _remove(self, token: tuple[str, str]) -> None:
        message_id, emoji_type = token
        await self._channel._get_client().delete(f"/im/v1/messages/{message_id}/reactions/{emoji_type}", headers=await self._channel._auth_headers())
    async def _add(self, message: IncomingMessage, state: str) -> tuple[str, str] | None:
        message_id = message.metadata.get("message_id")
        if not isinstance(message_id, str) or not message_id: return None
        emoji_type = FEISHU_STATUS_EMOJI[state]
        resp = await self._channel._get_client().post(f"/im/v1/messages/{message_id}/reactions", json={"reaction_type": {"emoji_type": emoji_type}}, headers=await self._channel._auth_headers())
        if resp.status_code >= 400 or resp.json().get("code") != 0: self._disable("invalid_emoji_type"); return None
        resp.raise_for_status(); return (message_id, emoji_type)

NULL_STATUS_REACTOR = NullStatusReactor()
