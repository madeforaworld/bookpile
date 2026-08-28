"""Tests for the fixed safety core.

These assert the behaviours that must never regress. Run:
    python3 -m unittest discover -s safety/tests -t .
"""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from safety import (Allowlist, AllowlistError, IdempotencyStore,
                    ValidationError, redact, validate_intent)


class TestAllowlist(unittest.TestCase):
    def test_permits_only_listed_user(self):
        a = Allowlist.from_config("111,222")
        self.assertTrue(a.permits(111))
        self.assertFalse(a.permits(333))

    def test_empty_allowlist_refuses_to_start(self):
        with self.assertRaises(AllowlistError):
            Allowlist.from_config("")
        with self.assertRaises(AllowlistError):
            Allowlist.from_config(None)

    def test_usernames_rejected(self):
        # usernames are reassignable; trusting one is a security bug
        with self.assertRaises(AllowlistError):
            Allowlist.from_config("@someone,222")

    def test_string_id_denied_not_coerced(self):
        a = Allowlist.from_config("111")
        self.assertFalse(a.permits("111"))

    def test_bool_is_not_an_int(self):
        a = Allowlist.from_config("1")
        self.assertFalse(a.permits(True))

    def test_chat_scope_enforced_when_set(self):
        a = Allowlist.from_config("111", "999")
        self.assertTrue(a.permits(111, 999))
        self.assertFalse(a.permits(111, 1000))
        self.assertFalse(a.permits(111, None))

    def test_chat_ignored_when_unset(self):
        a = Allowlist.from_config("111")
        self.assertTrue(a.permits(111, 12345))


class TestValidation(unittest.TestCase):
    def test_minimal_add(self):
        i = validate_intent({"intent": "add_book", "title": "Example Book"})
        self.assertEqual(i.title, "Example Book")

    def test_unknown_intent_rejected(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "delete_everything", "book_ref": "x"})

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "add_book", "title": "X", "sql": "DROP TABLE books"})

    def test_relative_date_rejected(self):
        # "today" must be resolved server-side, never by the model
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "set_reading_status", "book_ref": "X",
                             "status": "finished", "date": "today"})

    def test_impossible_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "set_reading_status", "book_ref": "X",
                             "status": "finished", "date": "2026-02-31"})

    def test_rating_bounds(self):
        for bad in (0, 6, 4.5, True, "4"):
            with self.assertRaises(ValidationError):
                validate_intent({"intent": "rate_book", "book_ref": "X", "rating": bad})
        self.assertEqual(validate_intent(
            {"intent": "rate_book", "book_ref": "X", "rating": 4}).rating, 4)

    def test_owned_three_valued(self):
        for value in (True, False, None):
            i = validate_intent({"intent": "set_owned", "book_ref": "X", "owned": value})
            self.assertIs(i.owned, value)
            self.assertTrue(i.owned_present)

    def test_owned_required_for_set_owned(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "set_owned", "book_ref": "X"})

    def test_low_confidence_refuses_to_write(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "add_book", "title": "X", "confidence": 0.4})

    def test_null_byte_rejected(self):
        with self.assertRaises(ValidationError):
            validate_intent({"intent": "add_book", "title": "bad\x00title"})

    def test_non_dict_rejected(self):
        for bad in ("add_book", None, [1], 7):
            with self.assertRaises(ValidationError):
                validate_intent(bad)


class TestIdempotency(unittest.TestCase):
    def test_once_claims_a_key_exactly_once(self):
        s = IdempotencyStore()
        self.assertTrue(s.once("msg:1"))
        self.assertFalse(s.once("msg:1"))
        self.assertTrue(s.once("msg:2"))

    def test_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "idem.json"
            self.assertTrue(IdempotencyStore(path).once("msg:1"))
            self.assertFalse(IdempotencyStore(path).once("msg:1"))

    def test_corrupt_store_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "idem.json"
            path.write_text("{ not json")
            self.assertTrue(IdempotencyStore(path).once("msg:1"))

    def test_capacity_evicts_oldest(self):
        s = IdempotencyStore(capacity=2)
        s.once("a"); s.once("b"); s.once("c")
        self.assertFalse(s.seen("a"))
        self.assertTrue(s.seen("c"))


class TestRedaction(unittest.TestCase):
    def test_bot_token(self):
        self.assertNotIn("AAH", redact("token 123456789:AAHrandomlookingsecretvalue00"))  # privacy-check: test-fixture

    def test_home_path(self):
        self.assertEqual(redact("at /home/someone/vault/x.md"), "at <home>/vault/x.md")  # privacy-check: test-fixture

    def test_email_and_tailnet(self):
        out = redact("a@b.com on host-1.ts.net")  # privacy-check: test-fixture
        self.assertNotIn("a@b.com", out)
        self.assertNotIn("host-1.ts.net", out)  # privacy-check: test-fixture

    def test_keyed_secret(self):
        self.assertIn("<redacted>", redact("api_key = sk-abcdef123456"))

    def test_non_string_input(self):
        self.assertIsInstance(redact({"a": 1}), str)


if __name__ == "__main__":
    unittest.main()
