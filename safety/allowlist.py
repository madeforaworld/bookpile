"""Numeric allowlist, checked on every inbound message. Fails closed."""
from __future__ import annotations
from dataclasses import dataclass


class AllowlistError(Exception):
    """Raised at startup for a configuration that cannot be trusted."""


def _parse_ids(raw: str | None, field: str) -> frozenset[int]:
    if raw is None:
        return frozenset()
    out = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            # A non-numeric entry means someone pasted a @username. Usernames
            # are mutable and reassignable; trusting one is a security bug.
            raise AllowlistError(
                f"{field} must contain numeric IDs only; got {part!r}"
            ) from None
    return frozenset(out)


@dataclass(frozen=True)
class Allowlist:
    users: frozenset[int]
    chats: frozenset[int]

    @classmethod
    def from_config(cls, users: str | None, chats: str | None = None) -> "Allowlist":
        parsed_users = _parse_ids(users, "allowed_users")
        if not parsed_users:
            # An empty user allowlist would admit nobody, which is safe, but it
            # is almost always a misconfiguration. Refuse to start rather than
            # look broken at runtime.
            raise AllowlistError(
                "allowed_users is empty — refusing to start. An intake adapter "
                "with no allowlist cannot be operated safely."
            )
        return cls(users=parsed_users, chats=_parse_ids(chats, "allowed_chats"))

    def permits(self, user_id: object, chat_id: object = None) -> bool:
        """True only if this sender is explicitly allowed.

        Anything unexpected — a string id, None, a float, a bool — is denied.
        There is no coercion here on purpose.
        """
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            return False
        if user_id not in self.users:
            return False
        if self.chats:
            if not isinstance(chat_id, int) or isinstance(chat_id, bool):
                return False
            if chat_id not in self.chats:
                return False
        return True
