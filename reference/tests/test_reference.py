"""Reference implementation tests.

The conformance vectors define correctness; these cover implementation detail
the vectors deliberately do not reach into.
"""
import sys, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reference"))

from bookpile.adapters import SQLiteRepository
from bookpile.intake.cli import CLIIntake
from bookpile.intake.telegram import TelegramIntake
from bookpile.models import BookRecord, Reading, Setting, slugify
from bookpile.service import AmbiguousReference, LibraryService, NotFound
from safety import Allowlist, IdempotencyStore

TODAY = date(2026, 8, 28)


def service():
    return LibraryService(SQLiteRepository(), today=lambda: TODAY)


class TestModel(unittest.TestCase):
    def test_slug_strips_traversal(self):
        self.assertEqual(slugify("../../etc/passwd"), "etc-passwd")

    def test_slug_never_empty(self):
        self.assertEqual(slugify("!!!"), "untitled")

    def test_fictional_setting_rejects_anchor_year(self):
        with self.assertRaises(ValueError):
            Setting(kind="fictional", anchor_year=1900)

    def test_finished_reading_requires_a_date(self):
        with self.assertRaises(ValueError):
            Reading(started_at="2026-01-01", outcome="finished")

    def test_future_schema_version_refused(self):
        with self.assertRaises(ValueError):
            BookRecord.from_dict({"book_id": "x", "title": "X", "schema_version": 99})

    def test_derived_rating_is_latest_non_null(self):
        b = BookRecord(book_id="x", title="X", readings=(
            Reading("2025-01-01", "2025-01-05", "finished", 3),
            Reading("2026-01-01", "2026-01-05", "finished", None)))
        self.assertEqual(b.rating, 3)

    def test_nulls_survive_serialization(self):
        d = BookRecord(book_id="x", title="X").to_dict()
        for key in ("owned", "page_count", "first_published", "rating", "sessions"):
            self.assertIn(key, d)
            self.assertIsNone(d[key])


class TestService(unittest.TestCase):
    def test_paused_leaves_reading_open(self):
        s = service()
        s.add_book("A")
        s.set_reading_status("A", "reading")
        s.set_reading_status("A", "paused")
        book = s.resolve("A")
        self.assertEqual(book.status, "paused")
        self.assertEqual(book.readings[-1].outcome, "in_progress")

    def test_abandon_then_finish_keeps_both(self):
        s = service()
        s.add_book("A")
        s.set_reading_status("A", "reading", "2025-01-01")
        s.set_reading_status("A", "abandoned", "2025-02-01")
        s.set_reading_status("A", "reading", "2026-01-01")
        s.set_reading_status("A", "finished", "2026-02-01")
        book = s.resolve("A")
        self.assertEqual(len(book.readings), 2)
        self.assertEqual([r.outcome for r in book.readings], ["abandoned", "finished"])

    def test_added_at_set_once(self):
        s = service()
        s.add_book("A")
        first = s.resolve("A").added_at
        s.set_reading_status("A", "reading")
        s.set_owned("A", True)
        self.assertEqual(s.resolve("A").added_at, first)

    def test_ambiguity_raises_rather_than_guessing(self):
        s = service()
        s.add_book("The Long Recension")
        s.add_book("The Long Winter")
        with self.assertRaises(AmbiguousReference):
            s.resolve("The Long")

    def test_missing_book_raises(self):
        with self.assertRaises(NotFound):
            service().resolve("nothing")


class TestTelegramPolicy(unittest.TestCase):
    """The network path is untested; these cover the guards around it."""

    class _OfflineTelegram(TelegramIntake):
        """No network in tests. Replies are captured, never sent."""
        def __init__(self, **kw):
            super().__init__(**kw)
            self.sent = []

        def _call(self, method, **params):
            self.sent.append((method, params))
            return {"ok": True, "result": []}

    def _intake(self):
        s = service()
        s.add_book("Salt in the Wiring")
        return self._OfflineTelegram(
            token="unused", allowlist=Allowlist.from_config("111"),
            handler=CLIIntake(s), idempotency=IdempotencyStore())

    @staticmethod
    def _update(uid, text, update_id=1):
        return {"update_id": update_id,
                "message": {"from": {"id": uid}, "chat": {"id": uid}, "text": text}}

    def test_unauthorized_sender_ignored_silently(self):
        t = self._intake()
        self.assertIsNone(t.handle_update(self._update(999, "start Salt in the Wiring")))
        self.assertEqual(t.handler.service.resolve("Salt in the Wiring").status, "to_read")
        self.assertEqual(t.sent, [], "nothing may be sent to an unauthorized sender")

    def test_duplicate_update_applies_once(self):
        t = self._intake()
        u = self._update(111, "start Salt in the Wiring", update_id=7)
        t.handle_update(u)
        t.handle_update(u)
        self.assertEqual(len(t.handler.service.resolve("Salt in the Wiring").readings), 1)

    def test_non_text_message_ignored(self):
        t = self._intake()
        self.assertIsNone(t.handle_update(
            {"update_id": 3, "message": {"from": {"id": 111}, "chat": {"id": 111},
                                         "photo": [{"file_id": "x"}]}}))

    def test_audit_line_omits_message_body(self):
        t = self._intake()
        line = t.audit_line(self._update(111, "finished My Private Book"), "set_status")
        self.assertNotIn("My Private Book", line)


if __name__ == "__main__":
    unittest.main()
