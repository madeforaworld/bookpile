#!/usr/bin/env python3
"""Conformance runner.

Executes the vectors against an implementation. The vectors are the contract;
this runner is just the harness that applies them. A generated Bookpile build
is conformant when it passes these, whatever its internals look like.

    python3 conformance/runner.py                 # all suites, all adapters
    python3 conformance/runner.py --suite metrics
"""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reference"))

from bookpile import projection
from bookpile.adapters import MarkdownVaultRepository, SQLiteRepository
from bookpile.intents import parse
from bookpile.models import BookRecord, Reading, Setting, slugify
from bookpile.service import AmbiguousReference, LibraryService, NotFound
from safety import ValidationError, validate_intent

FIXED_TODAY = date(2026, 8, 28)


class VectorFailure(Exception):
    pass


# ---------- building the "given" state ----------

def make_record(spec: dict) -> BookRecord:
    title = spec["title"]
    authors = tuple(spec.get("authors", ()))
    readings = tuple(
        Reading(started_at=r.get("started_at"), finished_at=r.get("finished_at"),
                outcome=r.get("outcome", "in_progress"), rating=r.get("rating"))
        for r in spec.get("readings", ())
    )
    status = spec.get("status")
    if status is None:
        status = "finished" if any(r.outcome == "finished" for r in readings) else (
            "reading" if readings else "to_read")
    return BookRecord(
        book_id=slugify(title, authors[0] if authors else ""),
        title=title, authors=authors, status=status,
        owned=spec.get("owned"),
        added_at=spec.get("added_at", "2025-01-01"),
        added_at_source=spec.get("added_at_source", "manual"),
        readings=readings,
        page_count=spec.get("page_count"),
        first_published=spec.get("first_published"),
        isbn13=spec.get("isbn13"),
        setting=Setting.from_dict(spec.get("setting")),
    )


def build_repo(kind: str, workdir: Path):
    if kind == "sqlite":
        return SQLiteRepository(workdir / "library.sqlite")
    return MarkdownVaultRepository(workdir / "library")


# ---------- assertions ----------

def check(condition: bool, message: str) -> None:
    if not condition:
        raise VectorFailure(message)


def assert_book(service: LibraryService, expect: dict) -> None:
    book = service.resolve(expect["ref"])
    for key, want in expect.items():
        if key == "ref":
            continue
        if key == "reading_count":
            got = len(book.readings)
        elif key == "completions":
            got = len(book.completions())
        elif key == "authors":
            got = list(book.authors)
        else:
            got = getattr(book, key)
        check(got == want, f"{expect['ref']}.{key}: expected {want!r}, got {got!r}")


def assert_projection(result, then: dict) -> None:
    if "expect" in then:
        for key, want in then["expect"].items():
            got = result[key]
            if isinstance(want, float) and got is not None:
                check(abs(got - want) < 1e-9, f"{key}: expected {want}, got {got}")
            else:
                check(got == want, f"{key}: expected {want!r}, got {got!r}")
    if "expect_bucket" in then:
        want = then["expect_bucket"]
        row = next((b for b in result["buckets"] if b["label"] == want["label"]), None)
        check(row is not None, f"no bucket {want['label']!r}")
        check(row["count"] == want["count"],
              f"bucket {want['label']}: expected {want['count']}, got {row['count']}")
    if "expect_excluded" in then:
        for key, want in then["expect_excluded"].items():
            got = result["excluded"].get(key)
            check(got == want, f"excluded.{key}: expected {want}, got {got}")
    if "expect_field" in then:
        want = then["expect_field"]
        row = next((f for f in result["fields"] if f["field"] == want["field"]), None)
        check(row is not None, f"no field {want['field']!r}")
        for k in ("present", "total"):
            check(row[k] == want[k], f"{want['field']}.{k}: expected {want[k]}, got {row[k]}")
    if "point_count" in then:
        check(len(result["points"]) == then["point_count"],
              f"points: expected {then['point_count']}, got {len(result['points'])}")
    if "status_keys" in then:
        got = [s["status"] for s in result["statuses"]]
        check(got == then["status_keys"], f"statuses: expected {then['status_keys']}, got {got}")
    if "excludes_metrics" in then:
        for m in then["excludes_metrics"]:
            check(m not in result, f"{m} should not be offered for this data")


# ---------- executing one vector ----------

def run_vector(vec: dict, adapter: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        repo = build_repo(adapter, workdir)
        service = LibraryService(repo, today=lambda: FIXED_TODAY)

        for spec in vec["given"].get("books", []):
            repo.upsert_book(make_record(spec))

        when, then = vec["when"], vec["then"]
        expected_error = then.get("error")

        try:
            if "reload" in when:
                repo = build_repo(adapter, workdir)          # fresh handle, same store
                service = LibraryService(repo, today=lambda: FIXED_TODAY)

            elif "upsert_with" in when:
                spec = when["upsert_with"]
                book = service.resolve(spec["ref"])
                repo.upsert_book(book.with_(**{k: v for k, v in spec.items() if k != "ref"}))

            elif "upsert_twice" in when:
                book = service.resolve(when["upsert_twice"]["ref"])
                repo.upsert_book(book)
                repo.upsert_book(book)

            elif "validate" in when:
                try:
                    validate_intent(when["validate"])
                    rejected = False
                except ValidationError:
                    rejected = True
                check(rejected == then["rejected"],
                      f"rejected: expected {then['rejected']}, got {rejected}")
                return

            elif "deliver_twice" in when or "deliver" in when:
                from safety import IdempotencyStore
                store = IdempotencyStore()
                if "deliver_twice" in when:
                    d = when["deliver_twice"]
                    deliveries = [d, d]
                else:
                    deliveries = when["deliver"]
                for d in deliveries:
                    if not store.once(IdempotencyStore.key("msg", d["message_id"])):
                        continue          # duplicate delivery: drop before any write
                    raw = parse(d["message"])
                    if raw is not None:
                        dispatch(service, validate_intent(raw))

            elif "project" in when:
                books = repo.list_books()
                name = when["project"]
                if name == "summary":
                    result = projection.summary(books, repo.capabilities(),
                                                year=when.get("year", "2026"))
                elif name == "available_metrics":
                    result = projection.available_metrics(books)
                else:
                    result = getattr(projection, name)(books)
                assert_projection(result, then)
                return

            elif "noop" not in when:
                messages = when.get("messages") or [when["message"]]
                for text in messages:
                    raw = parse(text)
                    if raw is None:
                        check(then.get("unparsed") is True,
                              f"message did not parse: {text!r}")
                        continue
                    intent = validate_intent(raw)
                    dispatch(service, intent)

        except (AmbiguousReference, NotFound, ValidationError, ValueError) as exc:
            if expected_error and type(exc).__name__ == expected_error:
                return
            raise VectorFailure(f"unexpected {type(exc).__name__}: {exc}") from None

        if expected_error:
            raise VectorFailure(f"expected {expected_error}, but nothing was raised")

        if "library_size" in then:
            got = len(repo.list_books())
            check(got == then["library_size"],
                  f"library_size: expected {then['library_size']}, got {got}")
        if "book" in then:
            assert_book(service, then["book"])
        if then.get("no_path_escape"):
            files = list(Path(workdir).rglob("*"))
            check(all(workdir in f.resolve().parents or f.resolve() == workdir for f in files),
                  "a record escaped the storage root")


def dispatch(service: LibraryService, intent) -> None:
    if intent.intent == "add_book":
        service.add_book(intent.title, intent.authors, intent.categories)
    elif intent.intent == "set_reading_status":
        service.set_reading_status(intent.book_ref, intent.status, intent.date)
        if intent.rating is not None:
            service.rate_book(intent.book_ref, intent.rating)
    elif intent.intent == "set_owned":
        service.set_owned(intent.book_ref, intent.owned)
    elif intent.intent == "rate_book":
        service.rate_book(intent.book_ref, intent.rating)
    elif intent.intent == "search_library":
        service.search_library(intent.query)


# ---------- driver ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", help="run one suite only")
    ap.add_argument("--adapter", default=None, help="sqlite or markdown")
    args = ap.parse_args()

    suites = sorted((ROOT / "conformance" / "vectors").glob("*.json"))
    if args.suite:
        suites = [s for s in suites if s.stem == args.suite]
        if not suites:
            print(f"no suite named {args.suite!r}")
            return 2

    adapters = [args.adapter] if args.adapter else ["sqlite", "markdown"]
    total = failed = 0
    failures: list[str] = []

    for path in suites:
        data = json.loads(path.read_text())
        # storage vectors are adapter-specific; the rest need one pass only
        run_on = adapters if data["suite"] == "storage" else adapters[:1]
        for adapter in run_on:
            label = f"{data['suite']}[{adapter}]" if data["suite"] == "storage" else data["suite"]
            print(f"\n{label}")
            for vec in data["vectors"]:
                total += 1
                try:
                    run_vector(vec, adapter)
                    print(f"  PASS  {vec['id']}  ({vec.get('invariant', '-')})")
                except VectorFailure as exc:
                    failed += 1
                    failures.append(f"{label}/{vec['id']}: {exc}")
                    print(f"  FAIL  {vec['id']}  ({vec.get('invariant', '-')})\n        {exc}")
                except Exception as exc:  # noqa: BLE001 - report, do not mask
                    failed += 1
                    failures.append(f"{label}/{vec['id']}: {type(exc).__name__}: {exc}")
                    print(f"  ERROR {vec['id']}: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 62)
    print(f"{total - failed}/{total} vectors passed")
    if failures:
        print("\nfailures:")
        for f in failures:
            print("  - " + f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
