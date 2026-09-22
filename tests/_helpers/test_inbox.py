"""Unit tests for `_helpers.inbox`."""

import json
from datetime import date
from pathlib import Path

import pytest

from _helpers.constants import (DEFAULT_PROFILE_NAME, INBOX_ARCHIVE_MAX_LINES,
                                INBOX_CATEGORIES_FILE_NAME, INBOX_FILE_NAME,
                                INBOX_PROFILES_FILE_NAME)
from _helpers.inbox import (append_archive, ensure_inbox_file, export_lookups, read_inbox,
                            stamp_imported, write_inbox)


def make_line(**overrides: object) -> str:
    """Builds one well-formed inbox line, with `overrides` applied to the defaults."""
    payload: dict[str, object] = {
        "type": "expense",
        "date": "2026-09-21",
        "amount": 12.5,
        "category": "Groceries",
        "description": "lidl",
        "profile": "Personal",
    }
    payload.update(overrides)
    return json.dumps(payload)


def write_lines(directory: Path, *lines: str) -> None:
    """Writes `lines` into the directory's inbox file."""
    (directory / INBOX_FILE_NAME).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


class TestReadInbox:
    """Tests for `read_inbox`."""

    def test_parses_a_well_formed_batch(self, tmp_path: Path) -> None:
        """Every field of a valid line makes it onto the resulting entry."""
        write_lines(tmp_path, make_line(), make_line(category="Transport", description="metro"))

        entries, malformed = read_inbox(tmp_path)

        assert malformed == []
        assert len(entries) == 2
        assert entries[0].day == date(2026, 9, 21)
        assert entries[0].cost == pytest.approx(12.5)
        assert entries[0].category == "Groceries"
        assert entries[0].description == "lidl"
        assert entries[0].profile == "Personal"
        assert entries[1].category == "Transport"

    def test_returns_empty_when_the_directory_does_not_exist(self, tmp_path: Path) -> None:
        """A folder iCloud hasn't created yet is an empty inbox, not an error."""
        assert read_inbox(tmp_path / "missing") == ([], [])

    def test_returns_empty_when_the_file_does_not_exist(self, tmp_path: Path) -> None:
        """An existing folder with no inbox file yet is an empty inbox."""
        assert read_inbox(tmp_path) == ([], [])

    def test_a_malformed_line_does_not_discard_the_valid_lines_beside_it(self, tmp_path: Path) -> None:
        """Lines are parsed independently, so one bad line only costs that line."""
        write_lines(tmp_path, make_line(), "{not json", make_line(category="Transport"))

        entries, malformed = read_inbox(tmp_path)

        assert [entry.category for entry in entries] == ["Groceries", "Transport"]
        assert malformed == ["{not json"]

    def test_blank_lines_are_skipped_entirely(self, tmp_path: Path) -> None:
        """A trailing newline or a stray blank line is neither an entry nor a rejection."""
        write_lines(tmp_path, make_line(), "", "   ")

        entries, malformed = read_inbox(tmp_path)

        assert len(entries) == 1
        assert malformed == []

    @pytest.mark.parametrize("missing", ["amount", "category"])
    def test_rejects_an_entry_missing_a_required_field(self, tmp_path: Path, missing: str) -> None:
        """A line without one of the fields that has no sensible default is rejected."""
        payload = json.loads(make_line())
        del payload[missing]
        line = json.dumps(payload)
        write_lines(tmp_path, line)

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert malformed == [line]

    def test_a_missing_description_defaults_to_empty(self, tmp_path: Path) -> None:
        """An expense without a description still imports."""
        payload = json.loads(make_line())
        del payload["description"]
        write_lines(tmp_path, json.dumps(payload))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].description == ""

    def test_a_missing_date_defaults_to_today(self, tmp_path: Path) -> None:
        """Omitting the date saves the Shortcut a custom date-format action."""
        payload = json.loads(make_line())
        del payload["date"]
        write_lines(tmp_path, json.dumps(payload))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].day == date.today()

    def test_a_missing_profile_defaults_to_the_default_profile(self, tmp_path: Path) -> None:
        """Omitting the profile saves the Shortcut a second picker."""
        payload = json.loads(make_line())
        del payload["profile"]
        write_lines(tmp_path, json.dumps(payload))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].profile == DEFAULT_PROFILE_NAME

    def test_accepts_the_display_format_a_shortcut_sends(self, tmp_path: Path) -> None:
        """Pinning the exact shape an iPhone Shortcut's Current Date variable produces.

        Without a Format Date action the value arrives in the phone's display style, and the
        trailing clock time has to be dropped since an expense is dated to a day.
        """
        write_lines(tmp_path, make_line(date="22 Sep 2026 at 11:16"))

        entries, malformed = read_inbox(tmp_path)

        assert malformed == []
        assert entries[0].day == date(2026, 9, 22)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-09-22", date(2026, 9, 22)),
            ("2026-09-22T11:16:00", date(2026, 9, 22)),
            ("22 Sep 2026", date(2026, 9, 22)),
            ("22 September 2026", date(2026, 9, 22)),
            ("Sep 22 2026", date(2026, 9, 22)),
            ("22 Sep 2026 at 11:16", date(2026, 9, 22)),
            ("22 Sep 2026 um 11:16", date(2026, 9, 22)),
            ("22 Sep 2026 at 11:16:59", date(2026, 9, 22)),
            ("22 Sep 2026 at 1:16 PM", date(2026, 9, 22)),
            ("22.09.2026", date(2026, 9, 22)),
        ],
    )
    def test_accepts_common_date_shapes(self, tmp_path: Path, raw: str, expected: date) -> None:
        """Each accepted format resolves to the same day."""
        write_lines(tmp_path, make_line(date=raw))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].day == expected

    def test_slash_dates_are_read_day_first(self, tmp_path: Path) -> None:
        """European convention, matching how the app already reads amounts: 3 April, not 4 March."""
        write_lines(tmp_path, make_line(date="03/04/2026"))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].day == date(2026, 4, 3)

    def test_rejects_a_date_it_cannot_recognise(self, tmp_path: Path) -> None:
        """An unparseable date is a rejection, never a silent fallback to today."""
        write_lines(tmp_path, make_line(date="last tuesday"))

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert len(malformed) == 1

    def test_a_dated_entry_keeps_its_own_year(self, tmp_path: Path) -> None:
        """The year is what picks the target database, so an old entry must not drift to today."""
        write_lines(tmp_path, make_line(date="31 Dec 2025 at 23:58"))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].day == date(2025, 12, 31)

    def test_an_explicit_date_and_profile_still_win(self, tmp_path: Path) -> None:
        """The defaults only apply when the field is absent, never overriding what was sent."""
        write_lines(tmp_path, make_line(date="2024-03-04", profile="Shared"))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].day == date(2024, 3, 4)
        assert entries[0].profile == "Shared"

    @pytest.mark.parametrize("amount", [0, -5, 0.0])
    def test_rejects_a_non_positive_amount(self, tmp_path: Path, amount: float) -> None:
        """`Expense.cost` must be greater than zero, so such an entry never reaches review."""
        write_lines(tmp_path, make_line(amount=amount))

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert len(malformed) == 1

    def test_ignores_a_non_expense_entry_type(self, tmp_path: Path) -> None:
        """The `type` field reserves room for income later; unknown types are not imported."""
        write_lines(tmp_path, make_line(type="income"))

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert len(malformed) == 1

    def test_a_numeric_amount_is_reformatted_into_the_app_display_convention(self, tmp_path: Path) -> None:
        """A JSON number is dot-decimal, but the app's amount fields read '.' as thousands.

        Stringifying 12.5 to "12.5" would be re-read as 125 by `evaluate_expression`, so the
        entry stores the amount in the app's own convention instead.
        """
        write_lines(tmp_path, make_line(amount=12.5))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].cost == pytest.approx(12.5)
        assert entries[0].cost_expression == "12,50"

    def test_evaluates_an_arithmetic_amount_string_and_preserves_its_raw_text(self, tmp_path: Path) -> None:
        """A string amount follows the app convention and may contain arithmetic."""
        write_lines(tmp_path, make_line(amount="12,50 + 3"))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].cost == pytest.approx(15.5)
        assert entries[0].cost_expression == "12,50 + 3"

    def test_a_string_amount_uses_comma_as_the_decimal_separator(self, tmp_path: Path) -> None:
        """"1.234,56" is one thousand two hundred, matching `parse_amount`, not 1.234."""
        write_lines(tmp_path, make_line(amount="1.234,56"))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].cost == pytest.approx(1234.56)

    def test_recovers_an_unquoted_comma_decimal_amount(self, tmp_path: Path) -> None:
        """A Shortcut Number field on a comma-decimal phone emits invalid JSON: `"amount":58,7`.

        Pinning the exact line the iPhone actually produced, since that break is silent - JSON
        reads `58` and then chokes on the stray `7`.
        """
        write_lines(tmp_path, '{"amount":58,7,"category":"Other","description":"Test"}')

        entries, malformed = read_inbox(tmp_path)

        assert malformed == []
        assert entries[0].cost == pytest.approx(58.7)
        assert entries[0].category == "Other"

    def test_the_recovered_amount_reads_the_comma_as_a_decimal_separator(self, tmp_path: Path) -> None:
        """58,7 is fifty-eight point seven, not five hundred eighty-seven."""
        write_lines(tmp_path, '{"amount":1,50,"category":"Other"}')

        entries, _ = read_inbox(tmp_path)

        assert entries[0].cost == pytest.approx(1.5)

    def test_a_quoted_comma_decimal_amount_needs_no_repair(self, tmp_path: Path) -> None:
        """Quoting the amount in the Shortcut is the real fix, and parses the same way."""
        write_lines(tmp_path, make_line(amount="58,7"))

        entries, malformed = read_inbox(tmp_path)

        assert malformed == []
        assert entries[0].cost == pytest.approx(58.7)

    def test_a_plain_json_number_is_left_alone(self, tmp_path: Path) -> None:
        """Valid JSON decodes on the first attempt, so the repair never sees it."""
        write_lines(tmp_path, make_line(amount=58.7))

        entries, _ = read_inbox(tmp_path)

        assert entries[0].cost == pytest.approx(58.7)

    def test_still_rejects_json_the_repair_cannot_fix(self, tmp_path: Path) -> None:
        """The repair is narrow: it only quotes an amount, it doesn't salvage arbitrary junk."""
        write_lines(tmp_path, '{"amount":12.5,"category":oops}')

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert len(malformed) == 1

    def test_rejects_an_amount_that_is_not_a_number_or_expression(self, tmp_path: Path) -> None:
        """A non-numeric amount string is rejected rather than defaulted."""
        write_lines(tmp_path, make_line(amount="a lot"))

        entries, malformed = read_inbox(tmp_path)

        assert entries == []
        assert len(malformed) == 1

    def test_keeps_the_source_line_verbatim(self, tmp_path: Path) -> None:
        """The raw line is retained so it can be archived exactly as it arrived."""
        line = make_line()
        write_lines(tmp_path, line)

        entries, _ = read_inbox(tmp_path)

        assert entries[0].raw == line


class TestEnsureInboxFile:
    """Tests for `ensure_inbox_file`."""

    def test_creates_an_empty_inbox_when_there_is_none(self, tmp_path: Path) -> None:
        """The Shortcut's read-combine-save append needs the file to already exist."""
        ensure_inbox_file(tmp_path)

        assert (tmp_path / INBOX_FILE_NAME).read_text(encoding="utf-8") == ""

    def test_leaves_an_existing_inbox_untouched(self, tmp_path: Path) -> None:
        """Seeding must never clobber entries captured but not yet imported."""
        line = make_line()
        write_lines(tmp_path, line)

        ensure_inbox_file(tmp_path)

        entries, _ = read_inbox(tmp_path)
        assert [entry.raw for entry in entries] == [line]

    def test_does_not_create_the_folder_when_its_parent_is_missing(self, tmp_path: Path) -> None:
        """No iCloud container means no folder and no inbox are invented."""
        absent_container = tmp_path / "no-icloud-here"

        ensure_inbox_file(absent_container / "Financial Tracker")

        assert not absent_container.exists()


class TestWriteInbox:
    """Tests for `write_inbox`."""

    def test_keeps_only_the_given_lines(self, tmp_path: Path) -> None:
        """The inbox is rewritten wholesale, dropping anything not passed in."""
        kept = make_line(category="Transport")
        write_lines(tmp_path, make_line(), kept)

        write_inbox(tmp_path, [kept])

        entries, _ = read_inbox(tmp_path)
        assert [entry.category for entry in entries] == ["Transport"]

    def test_an_empty_list_empties_the_inbox(self, tmp_path: Path) -> None:
        """Importing everything leaves nothing pending."""
        write_lines(tmp_path, make_line())

        write_inbox(tmp_path, [])

        assert read_inbox(tmp_path) == ([], [])

    def test_creates_the_directory_when_it_is_missing(self, tmp_path: Path) -> None:
        """Writing into a folder iCloud hasn't synced yet creates it rather than failing."""
        directory = tmp_path / "new"

        write_inbox(directory, [make_line()])

        assert (directory / INBOX_FILE_NAME).is_file()

    def test_does_not_create_the_folder_when_its_parent_is_missing(self, tmp_path: Path) -> None:
        """Same guard as the lookup export: no iCloud container means no folder is invented."""
        absent_container = tmp_path / "no-icloud-here"

        write_inbox(absent_container / "Financial Tracker", [make_line()])

        assert not absent_container.exists()

    def test_round_trip_preserves_un_imported_lines(self, tmp_path: Path) -> None:
        """A read/import/rewrite cycle loses nothing that wasn't imported."""
        imported = make_line(description="imported")
        skipped = make_line(description="skipped")
        write_lines(tmp_path, imported, skipped)

        entries, _ = read_inbox(tmp_path)
        write_inbox(tmp_path, [entry.raw for entry in entries if entry.description == "skipped"])

        remaining, malformed = read_inbox(tmp_path)
        assert malformed == []
        assert [entry.description for entry in remaining] == ["skipped"]
        assert remaining[0].raw == skipped


class TestAppendArchive:
    """Tests for `append_archive`."""

    def test_appends_to_a_new_file(self, tmp_path: Path) -> None:
        """The first append creates the archive."""
        append_archive(tmp_path, "imported.jsonl", ["a", "b"])

        assert (tmp_path / "imported.jsonl").read_text(encoding="utf-8").splitlines() == ["a", "b"]

    def test_appends_after_the_existing_lines(self, tmp_path: Path) -> None:
        """Later appends land at the end, preserving arrival order."""
        append_archive(tmp_path, "imported.jsonl", ["a"])
        append_archive(tmp_path, "imported.jsonl", ["b"])

        assert (tmp_path / "imported.jsonl").read_text(encoding="utf-8").splitlines() == ["a", "b"]

    def test_does_nothing_when_there_are_no_lines(self, tmp_path: Path) -> None:
        """An empty append doesn't create the file or touch an existing one."""
        append_archive(tmp_path, "imported.jsonl", [])

        assert not (tmp_path / "imported.jsonl").exists()

    def test_a_file_exactly_at_the_cap_is_left_intact(self, tmp_path: Path) -> None:
        """The cap is inclusive - reaching it is not exceeding it."""
        append_archive(tmp_path, "imported.jsonl", [str(i) for i in range(INBOX_ARCHIVE_MAX_LINES)])

        lines = (tmp_path / "imported.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == INBOX_ARCHIVE_MAX_LINES
        assert lines[0] == "0"

    def test_trims_to_the_cap_when_it_is_exceeded_by_one(self, tmp_path: Path) -> None:
        """One line over the cap drops exactly the oldest line."""
        append_archive(tmp_path, "imported.jsonl", [str(i) for i in range(INBOX_ARCHIVE_MAX_LINES)])
        append_archive(tmp_path, "imported.jsonl", ["newest"])

        lines = (tmp_path / "imported.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == INBOX_ARCHIVE_MAX_LINES
        assert lines[0] == "1"
        assert lines[-1] == "newest"

    def test_keeps_the_most_recent_lines(self, tmp_path: Path) -> None:
        """Trimming discards the oldest entries, not the newest."""
        append_archive(tmp_path, "imported.jsonl", [str(i) for i in range(INBOX_ARCHIVE_MAX_LINES + 50)])

        lines = (tmp_path / "imported.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == INBOX_ARCHIVE_MAX_LINES
        assert lines[-1] == str(INBOX_ARCHIVE_MAX_LINES + 49)

    def test_a_batch_larger_than_the_cap_still_lands_on_the_cap(self, tmp_path: Path) -> None:
        """A single oversized append is trimmed the same way an accumulated file is."""
        append_archive(tmp_path, "rejected.jsonl", [str(i) for i in range(INBOX_ARCHIVE_MAX_LINES * 3)])

        lines = (tmp_path / "rejected.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == INBOX_ARCHIVE_MAX_LINES


class TestStampImported:
    """Tests for `stamp_imported`."""

    def test_adds_an_imported_at_timestamp(self, tmp_path: Path) -> None:
        """The stamped line keeps its original fields and gains `imported_at`."""
        stamped = json.loads(stamp_imported(make_line()))

        assert stamped["category"] == "Groceries"
        assert "imported_at" in stamped
        assert stamped["imported_at"].startswith(date.today().isoformat())

    def test_returns_the_line_unchanged_when_it_is_not_json(self) -> None:
        """An unstampable line is archived as-is rather than lost."""
        assert stamp_imported("{not json") == "{not json"


class TestExportLookups:
    """Tests for `export_lookups`."""

    def test_writes_and_round_trips_both_files(self, tmp_path: Path) -> None:
        """Both lists are written one entry per line, which is what the Shortcut splits on."""
        export_lookups(tmp_path, ["Groceries", "Transport"], ["Personal", "Shared"])

        categories = (tmp_path / INBOX_CATEGORIES_FILE_NAME).read_text(encoding="utf-8")
        profiles = (tmp_path / INBOX_PROFILES_FILE_NAME).read_text(encoding="utf-8")
        assert categories == "Groceries\nTransport\n"
        assert profiles.splitlines() == ["Personal", "Shared"]

    def test_an_entry_containing_a_newline_stays_on_one_line(self, tmp_path: Path) -> None:
        """A stray newline inside a name would otherwise become two picker options."""
        export_lookups(tmp_path, ["Food\nand drinks", "Transport"], ["Personal"])

        assert (tmp_path / INBOX_CATEGORIES_FILE_NAME).read_text(encoding="utf-8").splitlines() == [
            "Food and drinks",
            "Transport",
        ]

    def test_skips_blank_entries(self, tmp_path: Path) -> None:
        """A blank line would show up as an empty, unselectable picker option."""
        export_lookups(tmp_path, ["Groceries", "   ", ""], ["Personal"])

        assert (tmp_path / INBOX_CATEGORIES_FILE_NAME).read_text(encoding="utf-8").splitlines() == ["Groceries"]

    def test_an_empty_list_writes_an_empty_file(self, tmp_path: Path) -> None:
        """No categories yet is an empty file, not a missing one."""
        export_lookups(tmp_path, [], [])

        assert (tmp_path / INBOX_CATEGORIES_FILE_NAME).read_text(encoding="utf-8") == ""

    def test_creates_the_directory_when_it_is_missing(self, tmp_path: Path) -> None:
        """The exchange folder is created on first launch rather than being a prerequisite."""
        directory = tmp_path / "new"

        export_lookups(directory, ["Groceries"], ["Personal"])

        assert (directory / INBOX_CATEGORIES_FILE_NAME).is_file()

    def test_swallows_a_write_failure(self, tmp_path: Path) -> None:
        """Being unable to write to iCloud must never block startup."""
        blocked = tmp_path / "blocked"
        blocked.write_text("i am a file, not a directory", encoding="utf-8")

        export_lookups(blocked / "sub", ["Groceries"], ["Personal"])

        assert blocked.is_file()

    def test_does_not_create_the_folder_when_its_parent_is_missing(self, tmp_path: Path) -> None:
        """A missing parent means iCloud Drive isn't set up, so nothing is invented.

        Creating the tree anyway would leave an ordinary local folder that looks correct but
        never reaches the phone, which is worse than visibly doing nothing.
        """
        absent_container = tmp_path / "no-icloud-here"

        export_lookups(absent_container / "Financial Tracker", ["Groceries"], ["Personal"])

        assert not absent_container.exists()
