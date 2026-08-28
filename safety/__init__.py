"""Fixed safety core.

This package is NEVER generated. An agent building a Bookpile install copies it
verbatim and calls it; it does not reimplement, "improve" or inline it.

Four concerns, deliberately small enough to audit in one sitting:

    allowlist    who may speak to the bot at all      (fail-closed)
    validation   what a message is allowed to become  (strict, no coercion)
    idempotency  duplicate delivery must not duplicate writes
    redaction    what may appear in a log
"""
from .allowlist import Allowlist, AllowlistError
from .validation import Intent, ValidationError, validate_intent
from .idempotency import IdempotencyStore
from .redaction import redact

__all__ = ["Allowlist", "AllowlistError", "Intent", "ValidationError",
           "validate_intent", "IdempotencyStore", "redact"]
