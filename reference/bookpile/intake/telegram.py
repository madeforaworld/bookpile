"""Telegram intake — long polling, allowlist, idempotency.

No webhook and no inbound port: the host reaches out to Telegram, never the
other way round.

UNTESTED AGAINST THE LIVE API. The policy layer below is covered by the safety
tests and the safety vectors; the network path is not, because that needs a
real bot token. Do not describe this as verified until it has been run.
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .cli import CLIIntake

try:
    from safety import Allowlist, IdempotencyStore, redact
except ImportError:
    import pathlib, sys as _s
    _s.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
    from safety import Allowlist, IdempotencyStore, redact

API = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class TelegramIntake:
    token: str
    allowlist: Allowlist
    handler: CLIIntake
    idempotency: IdempotencyStore
    timeout: int = 50

    def _call(self, method: str, **params) -> dict:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params).encode()
        with urllib.request.urlopen(url, data=data, timeout=self.timeout + 10) as fh:
            return json.load(fh)

    def poll_once(self, offset: int | None = None) -> int | None:
        """One long-poll cycle. Returns the next offset."""
        payload = self._call("getUpdates", timeout=self.timeout,
                             **({"offset": offset} if offset is not None else {}))
        next_offset = offset
        for update in payload.get("result", []):
            next_offset = update["update_id"] + 1
            self.handle_update(update)
        return next_offset

    def handle_update(self, update: dict) -> str | None:
        """Policy layer. Every guard here fails closed."""
        message = update.get("message") or {}
        user_id = (message.get("from") or {}).get("id")
        chat_id = (message.get("chat") or {}).get("id")
        text = message.get("text")

        if not self.allowlist.permits(user_id, chat_id):
            # Silent. Never reveal capabilities to an unauthorized sender.
            return None
        if not isinstance(text, str):
            return None
        # Duplicate delivery must not duplicate a write.
        if not self.idempotency.once(IdempotencyStore.key("tg", update["update_id"])):
            return None

        reply = self.handler.handle(text)
        if chat_id is not None:
            self._call("sendMessage", chat_id=chat_id, text=reply)
        return reply

    def audit_line(self, update: dict, action: str) -> str:
        """Action, timestamp, opaque actor. Never the message body."""
        actor = (update.get("message", {}).get("from") or {}).get("id")
        return redact(f"action={action} actor={actor} update={update.get('update_id')}")
