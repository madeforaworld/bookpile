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
from bookpile.intents import parse
from bookpile.metadata import MetadataResult
from bookpile.service import AmbiguousReference, LibraryService, NotFound
from safety import Allowlist, IdempotencyStore, validate_intent

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

    def test_ambiguity_names_author_and_year_not_just_titles(self):
        s = service()
        s.add_book("The Long Recension", authors=["Tomas Bergqvist"], first_published=2011)
        s.add_book("The Long Winter")          # no author recorded, no year
        with self.assertRaises(AmbiguousReference) as ctx:
            s.resolve("The Long")
        message = str(ctx.exception)
        self.assertIn("Tomas Bergqvist", message)
        self.assertIn("2011", message)
        self.assertIn("unknown author", message, "a missing author must be stated, not omitted")

    def test_missing_book_raises(self):
        with self.assertRaises(NotFound):
            service().resolve("nothing")


class StubProvider:
    """No network in tests. Records calls, returns whatever it is told to."""
    def __init__(self, result=None, discoveries=(), boom=False):
        self.result, self.discoveries, self.boom = result, list(discoveries), boom
        self.enrich_calls, self.discover_calls = [], []

    def enrich(self, title, author=None):
        self.enrich_calls.append((title, author))
        if self.boom:
            raise RuntimeError("provider exploded")
        return self.result

    def discover(self, subjects, exclude_titles=None, limit=5):
        self.discover_calls.append((tuple(subjects), set(exclude_titles or ())))
        excl = {t.lower() for t in (exclude_titles or ())}
        return [m for m in self.discoveries if m.title.lower() not in excl][:limit]


class TestAcquisitionLanguage(unittest.TestCase):
    def test_recommended_book_is_known_to_be_unowned(self):
        raw = parse("Priya recommended The Copper Question")
        i = validate_intent(raw)
        self.assertEqual(i.intent, "add_book")
        self.assertIs(i.owned, False)

    def test_bought_sets_owned_true(self):
        i = validate_intent(parse("i bought The Copper Question"))
        self.assertEqual(i.intent, "set_owned")
        self.assertIs(i.owned, True)

    def test_plain_add_leaves_ownership_unknown(self):
        i = validate_intent(parse("add The Copper Question"))
        self.assertFalse(i.owned_present, "a bare add must not assert ownership either way")

    def test_buying_language_is_not_shelf_language(self):
        self.assertEqual(parse("what should i buy")["intent"], "discover")
        self.assertEqual(parse("what should i read next")["intent"], "recommend")


class TestRecommend(unittest.TestCase):
    def _svc(self):
        s = service()
        s.add_book("Short Historical", categories=["Historical"], page_count=180)
        s.add_book("Long Speculative", page_count=700)
        s.set_owned("Long Speculative", True)
        s.add_book("Already Reading")
        s.set_reading_status("Already Reading", "reading")
        return s

    def test_only_suggests_unread_books(self):
        titles = [p["book"].title for p in self._svc().recommend()]
        self.assertNotIn("Already Reading", titles)

    def test_vibe_moves_the_match_to_the_top(self):
        picks = self._svc().recommend("something short and historical")
        self.assertEqual(picks[0]["book"].title, "Short Historical")

    def test_every_pick_carries_a_reason(self):
        for pick in self._svc().recommend():
            self.assertTrue(pick["reason"], "an unexplained recommendation is not actionable")

    def test_empty_shelf_returns_nothing_not_an_error(self):
        self.assertEqual(service().recommend(), [])


class TestMetadata(unittest.TestCase):
    def _found(self, **kw):
        base = dict(title="X", first_published=1969, page_count=304,
                    isbn13="9780000000000", cover_url="https://example.invalid/c.jpg",
                    subjects=("Science fiction",), external_id="OL1W",
                    url="https://openlibrary.org/works/OL1W")
        base.update(kw)
        return MetadataResult(**base)

    def test_enrichment_fills_blanks(self):
        s = service(); s.metadata = StubProvider(self._found())
        s.add_book("X", enrich=True)
        b = s.resolve("X")
        self.assertEqual(b.first_published, 1969)
        self.assertEqual(b.page_count, 304)
        self.assertEqual(b.cover_ref, "https://example.invalid/c.jpg")

    def test_enrichment_never_overwrites_what_you_said(self):
        s = service(); s.metadata = StubProvider(self._found(page_count=999))
        s.add_book("X", page_count=123, enrich=True)
        self.assertEqual(s.resolve("X").page_count, 123)

    def test_cover_is_replace_never(self):
        s = service(); s.metadata = StubProvider(self._found())
        s.add_book("X", cover_ref="local/mine.jpg", enrich=True)
        self.assertEqual(s.resolve("X").cover_ref, "local/mine.jpg")

    def test_subjects_never_become_categories(self):
        s = service(); s.metadata = StubProvider(self._found())
        s.add_book("X", enrich=True)
        b = s.resolve("X")
        self.assertIn("Science fiction", b.subjects)
        self.assertEqual(b.categories, ())

    def test_provider_failure_does_not_block_the_write(self):
        s = service(); s.metadata = StubProvider(boom=True)
        s.add_book("X", enrich=True)
        self.assertIsNotNone(s.resolve("X"), "the book must be added even if lookup fails")

    def test_no_lookup_unless_asked(self):
        s = service(); s.metadata = StubProvider(self._found())
        s.add_book("X")
        self.assertEqual(s.metadata.enrich_calls, [], "metadata lookups are opt-in")

    def test_discover_excludes_books_you_already_have(self):
        s = service(); s.add_book("Owned Title", categories=["History"])
        s.metadata = StubProvider(discoveries=[
            MetadataResult(title="Owned Title"), MetadataResult(title="New Title")])
        self.assertEqual([m.title for m in s.discover()], ["New Title"])

    def test_discover_without_a_provider_is_empty_not_an_error(self):
        s = service(); s.add_book("A")
        self.assertEqual(s.discover(), [])


class TestTelegramPolicy(unittest.TestCase):
    """The network path is untested; these cover the guards around it."""

    class _OfflineTelegram(TelegramIntake):
        """No network in tests. Replies are captured, never sent."""
        def __init__(self, **kw):
            super().__init__(**kw)
            self.sent = []

        _queued = None

        def _call(self, method, **params):
            self.sent.append((method, params))
            if method == "getUpdates" and self._queued is not None:
                return self._queued
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

    def test_poll_once_advances_the_offset(self):
        t = self._intake()
        t._queued = {"ok": True, "result": [
            {"update_id": 10, "message": {"from": {"id": 111}, "chat": {"id": 111},
                                          "text": "start Salt in the Wiring"}},
            {"update_id": 11, "message": {"from": {"id": 111}, "chat": {"id": 111},
                                          "text": "finished Salt in the Wiring"}}]}
        nxt = t.poll_once(offset=10)
        self.assertEqual(nxt, 12, "offset must advance past the last update")
        self.assertEqual(t.handler.service.resolve("Salt in the Wiring").status, "finished")

    def test_poll_once_with_no_updates_keeps_offset(self):
        t = self._intake()
        t._queued = {"ok": True, "result": []}
        self.assertEqual(t.poll_once(offset=42), 42)

    def test_replies_go_to_the_originating_chat(self):
        t = self._intake()
        t.handle_update(self._update(111, "start Salt in the Wiring"))
        sends = [p for m, p in t.sent if m == "sendMessage"]
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0]["chat_id"], 111)

    def test_audit_line_omits_message_body(self):
        t = self._intake()
        line = t.audit_line(self._update(111, "finished My Private Book"), "set_status")
        self.assertNotIn("My Private Book", line)


if __name__ == "__main__":
    unittest.main()
