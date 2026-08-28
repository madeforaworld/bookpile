"""Log redaction.

The audit log records that an action happened, not what was said. These
patterns are the backstop for anything that reaches a log line anyway.
"""
from __future__ import annotations
import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b"), "<bot-token>"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*"), "Bearer <token>"),
    (re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----.*?-----END[^-]*PRIVATE KEY-----", re.S), "<private-key>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<aws-key>"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "<email>"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd)\b(\s*[:=]\s*)\S+"), r"\1\2<redacted>"),
    (re.compile(r"/(?:home|Users)/[^/\s]+"), "<home>"),
    (re.compile(r"\b[a-z0-9-]+\.ts\.net\b"), "<tailnet-host>"),
]


def redact(text: object) -> str:
    """Strip credentials, emails and local paths from a string bound for a log."""
    out = text if isinstance(text, str) else repr(text)
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out
