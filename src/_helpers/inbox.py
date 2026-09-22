"""Reads expenses captured on the iPhone from the shared iCloud Drive folder."""

import json
import re
from datetime import date, datetime
from logging import getLogger
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from .constants import (DEFAULT_PROFILE_NAME, INBOX_ARCHIVE_MAX_LINES,
                        INBOX_CATEGORIES_FILE_NAME, INBOX_FILE_NAME,
                        INBOX_PROFILES_FILE_NAME)
from .expression_parser import evaluate_expression
from .formatting import format_amount

logger = getLogger("financial_tracker")

ENTRY_TYPE_EXPENSE = "expense"

# an unquoted `"amount": 58,7` - what a Shortcut's Number field produces in any locale that uses
# a comma for decimals - is fatally invalid JSON, so it gets quoted before decoding and then
# read as an ordinary comma-decimal amount
_UNQUOTED_AMOUNT = re.compile(r'("amount"\s*:\s*)([0-9][0-9.,]*[0-9]|[0-9])(\s*[,}])')

# a trailing clock time, with or without its locale's connector word, as produced by a Shortcut
# sending Current Date rather than a Format Date result: "22 Sep 2026 at 11:16"
_TIME_SUFFIX = re.compile(
    r"\s*(?:\b(?:at|um|alle|kl)\b)?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?$",
    re.IGNORECASE,
)

# tried in order after ISO. Day-first throughout: this app already reads amounts with the
# European convention, so "03/04/2026" is 3 April, never 4 March
_DATE_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d.%m.%Y",
    "%d/%m/%Y",
)


@dataclass(frozen=True, kw_only=True)
class InboxEntry:
    """A single expense captured on the phone, parsed but not yet imported.

    This is deliberately *not* a `:class:DataContainer` subclass: it backs no table, it is a
    staging record that gets turned into an `:class:Expense` once reviewed.

    Attributes:
        day (date): The full date of the expense. Unlike `:class:Expense` (whose year is implied
            by the database file it lives in) an inbox entry carries its own year, since it has
            to decide for itself which year's database it belongs to. Defaults to today when the
            line omits it.
        cost (float): The evaluated cost of the expense (greater than zero).
        cost_expression (str): The cost as it should be redisplayed in an amount field, always
            in the app's display convention (see `:func:format_amount`).
        category (str): The category the phone sent. Not validated against the lookup list here
            - that happens at review time, where the user can remap it.
        description (str): The description of the expense.
        profile (str): The profile the entry should be imported into. Defaults to
            `:const:DEFAULT_PROFILE_NAME` when the line omits it.
        raw (str): The original line this entry was parsed from, kept verbatim so it can be
            archived exactly as it arrived.
    """

    day: date
    cost: float = Field(gt=0.0)
    cost_expression: str
    category: str
    description: str
    profile: str
    raw: str


def read_inbox(directory: Path) -> tuple[list[InboxEntry], list[str]]:
    """Reads and parses every pending entry in the inbox file.

    The inbox lives in iCloud Drive, so failure is expected rather than exceptional: the folder
    may not exist yet, the file may still be a dataless placeholder, or a line may have been
    written by a mis-edited Shortcut. A missing or unreadable inbox is an empty inbox, and each
    line is parsed independently so one bad line can't discard the good ones beside it.

    A file that simply isn't there yet is the normal state before the Shortcut has run, so it
    returns early rather than going through the tolerant-read path and logging a traceback.

    Args:
        directory (Path): The folder shared with the phone.

    Returns:
        tuple[list[`:class:InboxEntry`], list[str]]: The parsed entries, and the raw text of
            every line that couldn't be parsed.
    """
    logger.info("Called 'read_inbox'")

    path = directory / INBOX_FILE_NAME

    # the usual state before the Shortcut has ever run, and not worth a stack trace
    if not path.is_file():
        logger.debug(f"No inbox file at '{path}' yet.")
        return [], []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        logger.debug(f"Could not read the inbox at '{path}'.", exc_info=True)
        return [], []

    entries: list[InboxEntry] = []
    malformed: list[str] = []
    for line in lines:
        if not line.strip():
            continue

        entry = _parse_line(line)
        if entry is None:
            malformed.append(line)
        else:
            entries.append(entry)

    logger.debug(f"Read {len(entries)} pending entries ({len(malformed)} malformed) from '{path}'.")
    return entries, malformed


def ensure_inbox_file(directory: Path) -> None:
    """Creates an empty inbox file if the folder doesn't have one yet.

    The Shortcut appends by reading the inbox, combining, and saving it back, which fails
    outright on a file that doesn't exist - so its first ever run would error without this.
    An inbox that already exists is left completely alone: overwriting it would throw away
    entries captured but not yet imported.

    Args:
        directory (Path): The folder shared with the phone.
    """
    logger.info("Called 'ensure_inbox_file'")

    path = directory / INBOX_FILE_NAME
    if path.exists():
        return

    try:
        _ensure_directory(directory)
        path.touch()
        logger.debug(f"Seeded an empty inbox at '{path}'.")
    except Exception:
        logger.debug(f"Could not seed an inbox at '{path}'.", exc_info=True)


def write_inbox(directory: Path, lines: list[str]) -> None:
    """Rewrites the inbox file so it holds exactly `lines`.

    Only ever called with the lines that were neither imported nor discarded: an entry the user
    keeps skipping stays in the inbox indefinitely, since silently expiring un-imported expenses
    is the failure mode this whole design exists to avoid.

    Args:
        directory (Path): The folder shared with the phone.
        lines (list[str]): The raw lines to keep.
    """
    logger.info("Called 'write_inbox'")

    _write_lines(directory / INBOX_FILE_NAME, lines)


def append_archive(directory: Path, filename: str, lines: list[str]) -> None:
    """Appends `lines` to an archive file, then trims it back to its most recent entries.

    The archive is an audit trail, not the system of record - every imported row already lives
    in its yearly database - so it is capped at `:const:INBOX_ARCHIVE_MAX_LINES` lines rather
    than being allowed to grow forever. Trimming happens on every append instead of once per
    launch, so the cap holds even across many imports in a single session.

    Args:
        directory (Path): The folder shared with the phone.
        filename (str): The archive file to append to.
        lines (list[str]): The raw lines to append.
    """
    logger.info("Called 'append_archive'")

    if not lines:
        return

    path = directory / filename
    existing: list[str] = []
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            # readable-but-broken is worth a trace; simply not existing yet is not
            logger.debug(f"Could not read the archive at '{path}', starting it over.", exc_info=True)

    combined = [line for line in [*existing, *lines] if line.strip()]
    trimmed = combined[-INBOX_ARCHIVE_MAX_LINES:]
    if len(trimmed) < len(combined):
        logger.debug(f"Trimmed '{filename}' from {len(combined)} to {len(trimmed)} lines.")

    _write_lines(path, trimmed)


def stamp_imported(line: str) -> str:
    """Adds an `imported_at` timestamp to a line before it gets archived.

    Records when the row actually landed, which a back-dated entry's own `date` doesn't tell
    you. Purely for auditing - the archive is trimmed by line count, not by this timestamp.

    Args:
        line (str): The raw inbox line.

    Returns:
        str: The line with an `imported_at` key added, or unchanged if it couldn't be stamped.
    """
    try:
        payload = json.loads(line)
        payload["imported_at"] = datetime.now().isoformat(timespec="seconds")
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        logger.debug(f"Could not stamp line for the archive: {line}", exc_info=True)
        return line


def export_lookups(directory: Path, categories: list[str], profiles: list[str]) -> None:
    """Writes the category and profile lists out for the phone's Shortcut to read.

    Written as one entry per line, which the Shortcut turns into a picker with "Split Text" by
    new lines. Called on every launch so the pickers track the real lookup lists instead of a
    hardcoded copy that silently rots. Failure is logged and swallowed - not being able to
    write to iCloud must never block startup.

    Args:
        directory (Path): The folder shared with the phone.
        categories (list[str]): The current expense categories.
        profiles (list[str]): The profiles that currently have data.
    """
    logger.info("Called 'export_lookups'")

    for filename, values in ((INBOX_CATEGORIES_FILE_NAME, categories), (INBOX_PROFILES_FILE_NAME, profiles)):
        path = directory / filename
        try:
            _ensure_directory(path.parent)
            # a newline inside an entry would silently split it into two picker options
            lines = [value.replace("\n", " ").strip() for value in values if value.strip()]
            path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        except Exception:
            logger.debug(f"Could not export '{path}'.", exc_info=True)

    logger.debug(f"Exported {len(categories)} categories and {len(profiles)} profiles to '{directory}'.")


def _parse_line(line: str) -> InboxEntry | None:
    """Parses one inbox line into an `:class:InboxEntry`.

    Args:
        line (str): The raw line.

    Returns:
        `:class:InboxEntry` | None: The parsed entry, or `None` if the line is not a well-formed
            expense entry (bad JSON, missing field, unparseable date or amount, wrong `type`).
    """
    try:
        payload = _load_payload(line)

        if payload.get("type", ENTRY_TYPE_EXPENSE) != ENTRY_TYPE_EXPENSE:
            logger.debug(f"Ignoring non-expense inbox line: {line}")
            return None

        amount = payload["amount"]
        cost = _parse_cost(amount)

        return InboxEntry(
            # both of these are optional so the Shortcut needs neither a custom date format
            # nor a second picker: the common case is "today, my usual profile"
            day=_parse_day(payload["date"]) if payload.get("date") else date.today(),
            cost=cost,
            # a numeric amount is dot-decimal, which the app's amount fields would read as a
            # thousands separator, so it gets reformatted rather than stringified
            cost_expression=amount if isinstance(amount, str) else format_amount(cost),
            category=str(payload["category"]),
            description=str(payload.get("description", "")),
            profile=str(payload.get("profile") or DEFAULT_PROFILE_NAME),
            raw=line,
        )
    except Exception:
        logger.debug(f"Discarding malformed inbox line: {line}", exc_info=True)
        return None


def _load_payload(line: str) -> Any:
    """Decodes one inbox line, first repairing an unquoted comma-decimal amount if there is one.

    A Shortcut's Number field formats using the phone's locale, so an amount inserted into the
    JSON without quotes arrives as `"amount": 58,7` on a comma-decimal device - which is not
    valid JSON at all. Quoting it recovers the line and routes it down the same path as any
    other string amount, where the comma is read as the decimal separator.

    Args:
        line (str): The raw inbox line.

    Returns:
        Any: The decoded payload.

    Raises:
        json.JSONDecodeError: If the line is not valid JSON and quoting the amount doesn't fix it.
    """
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        repaired = _UNQUOTED_AMOUNT.sub(r'\1"\2"\3', line)
        if repaired == line:
            raise

        logger.debug(f"Quoted an unquoted comma-decimal amount to recover the line: {line}")
        return json.loads(repaired)


def _parse_day(value: Any) -> date:
    """Parses the `date` field of an inbox entry into the day the expense belongs to.

    ISO `YYYY-MM-DD` is the format to send, but a Shortcut's Current Date variable arrives in
    the phone's display style unless a Format Date action reshapes it, e.g.
    "22 Sep 2026 at 11:16" - so a few common shapes are accepted too. Any trailing clock time is
    dropped, since an expense is dated to a day rather than a moment.

    Slash- and dot-separated dates are read **day first**, matching the European convention the
    app's amount fields already use.

    Args:
        value (Any): The raw `date` value decoded from JSON.

    Returns:
        date: The parsed day.

    Raises:
        ValueError: If none of the accepted formats match.
    """
    raw = str(value).strip()

    # ISO first and before any trimming: stripping the time off "2026-09-22T11:16:00" would
    # leave a dangling "2026-09-22T" that no longer parses
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        pass

    text = _TIME_SUFFIX.sub("", raw).strip()

    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass

    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue

    raise ValueError(f"Unrecognised date: {value!r}")


def _parse_cost(amount: Any) -> float:
    """Parses the `amount` field of an inbox entry, which may be a number or an expression.

    A JSON number is unambiguous and taken as-is - that's what the Shortcut's "Ask for Number"
    action produces. A string goes through `:func:evaluate_expression`, so it follows the app's
    display convention ('.' for thousands, ',' for decimals) and may contain arithmetic, exactly
    like the cost field on the Expenses page.

    Args:
        amount (Any): The raw `amount` value decoded from JSON.

    Returns:
        float: The evaluated cost.

    Raises:
        ValueError: If `amount` is neither a number nor a well-formed expression string.
    """
    if isinstance(amount, bool):
        raise ValueError("The amount must be a number or an expression string.")

    if isinstance(amount, int | float):
        return float(amount)

    return evaluate_expression(str(amount))


def _ensure_directory(directory: Path) -> None:
    """Creates the exchange folder, but only inside a parent that already exists.

    Deliberately not `parents=True`: the parent here is the iCloud Drive container, and if that
    is missing then iCloud Drive isn't set up on this Mac. Creating it anyway would leave an
    ordinary local folder that looks right, never syncs to the phone, and reports success - so
    a missing container is surfaced as a failure instead.

    Args:
        directory (Path): The folder shared with the phone.

    Raises:
        FileNotFoundError: If `directory`'s parent doesn't exist.
    """
    if not directory.is_dir() and not directory.parent.is_dir():
        logger.debug(f"'{directory.parent}' does not exist - iCloud Drive looks unavailable.")

    directory.mkdir(exist_ok=True)


def _write_lines(path: Path, lines: list[str]) -> None:
    """Writes `lines` to `path`, one per line, creating the folder if needed.

    Args:
        path (Path): The file to write.
        lines (list[str]): The lines to write, without trailing newlines.
    """
    try:
        _ensure_directory(path.parent)
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    except Exception:
        logger.debug(f"Could not write '{path}'.", exc_info=True)
