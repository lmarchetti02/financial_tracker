"""Global (non-yearly) configuration store: category/source/kind lookup lists and app preferences."""

import sqlite3 as sq
from dataclasses import dataclass
from enum import Enum, auto
from logging import getLogger
from pathlib import Path

from _helpers.constants import (
    APP_DIRECTORY,
    CONFIG_DB_NAME,
    SYSTEM_CATEGORY_TRADING_FEE,
    SYSTEM_KIND_CREDIT,
    SYSTEM_KIND_DEBT,
    SYSTEM_KIND_INVESTMENT,
    SYSTEM_SOURCE_INVESTMENTS,
)

from .generic import DbLocation, get_db_path, list_year_profile_pairs

logger = getLogger("financial_tracker")


class LookupKind(Enum):
    """The three user-editable lookup lists backing the `category`/`source`/`kind` fields."""

    CATEGORIES = auto()
    SOURCES = auto()
    KINDS = auto()


_LOOKUP_TABLE = {
    LookupKind.CATEGORIES: "categories",
    LookupKind.SOURCES: "sources",
    LookupKind.KINDS: "kinds",
}

# (domain table, column) referencing each lookup, used for the in-use check and the rename cascade
_LOOKUP_REFERENCES = {
    LookupKind.CATEGORIES: ("expenses", "category"),
    LookupKind.SOURCES: ("income", "source"),
    LookupKind.KINDS: ("transfers", "kind"),
}

# seed data: (display label, is_system)
_SEED_CATEGORIES = [
    ("Couple", False),
    ("Education", False),
    ("Entertainment", False),
    ("Food and drinks", False),
    ("Subscriptions", False),
    ("Personal items", False),
    ("Presents", False),
    ("Travel", False),
    (SYSTEM_CATEGORY_TRADING_FEE, True),
    ("Capital loss", False),
    ("Taxes", False),
    ("Interest on debt", False),
    ("Other", False),
]
_SEED_SOURCES = [
    ("Salary", False),
    ("Presents", False),
    (SYSTEM_SOURCE_INVESTMENTS, True),
    ("Other", False),
]
_SEED_KINDS = [
    ("Loan", False),
    (SYSTEM_KIND_CREDIT, True),
    (SYSTEM_KIND_DEBT, True),
    (SYSTEM_KIND_INVESTMENT, True),
]
_SEED_DATA = {
    LookupKind.CATEGORIES: _SEED_CATEGORIES,
    LookupKind.SOURCES: _SEED_SOURCES,
    LookupKind.KINDS: _SEED_KINDS,
}


@dataclass(frozen=True)
class LookupOption:
    """A single entry in a category/source/kind lookup list."""

    name: str
    is_system: bool


def get_config_db_path() -> Path:
    """Returns the path to the global (non-yearly) configuration database file."""
    return APP_DIRECTORY / f"{CONFIG_DB_NAME}.db"


def initialize_config_db() -> None:
    """Creates the config database/tables and seeds their default entries, if not done yet."""
    logger.info("Called 'initialize_config_db'")

    APP_DIRECTORY.mkdir(exist_ok=True, parents=True)

    with sq.connect(get_config_db_path()) as connection:
        cursor = connection.cursor()

        cursor.execute("CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

        for kind, table in _LOOKUP_TABLE.items():
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table} (name TEXT PRIMARY KEY, is_system INTEGER NOT NULL DEFAULT 0)"
            )

            if cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > 0:
                continue

            cursor.executemany(
                f"INSERT INTO {table} (name, is_system) VALUES (?, ?)",
                [(label, int(is_system)) for label, is_system in _SEED_DATA[kind]],
            )
            logger.debug(f"Seeded '{table}' with its default entries.")

        # upgrade installs seeded before "Debt"/"Credit" became system-reserved
        cursor.execute(
            f"UPDATE {_LOOKUP_TABLE[LookupKind.KINDS]} SET is_system = 1 WHERE name IN (?, ?)",
            (SYSTEM_KIND_DEBT, SYSTEM_KIND_CREDIT),
        )
        logger.debug("Ensured 'Debt'/'Credit' kinds are marked system-reserved.")


def fetch_lookup_options(kind: LookupKind) -> list[LookupOption]:
    """Fetches every entry in a lookup list, sorted alphabetically.

    Args:
        kind (`:enum:LookupKind`): Which lookup list to fetch.

    Returns:
        list[LookupOption]: The entries, sorted by name.
    """
    logger.info("Called 'fetch_lookup_options'")

    table = _LOOKUP_TABLE[kind]
    with sq.connect(get_config_db_path()) as connection:
        rows = connection.execute(f"SELECT name, is_system FROM {table} ORDER BY name").fetchall()

    return [LookupOption(name=row[0], is_system=bool(row[1])) for row in rows]


def add_lookup_option(kind: LookupKind, name: str) -> None:
    """Adds a new entry to a lookup list.

    Args:
        kind (`:enum:LookupKind`): Which lookup list to add to.
        name (str): The new entry's display text.

    Raises:
        ValueError: If `name` is blank, or an entry with that name (case-insensitively) already exists.
    """
    logger.info("Called 'add_lookup_option'")

    name = name.strip()
    if not name:
        raise ValueError("The name cannot be blank.")

    table = _LOOKUP_TABLE[kind]
    with sq.connect(get_config_db_path()) as connection:
        existing = {row[0].lower() for row in connection.execute(f"SELECT name FROM {table}")}
        if name.lower() in existing:
            raise ValueError(f"'{name}' already exists.")

        connection.execute(f"INSERT INTO {table} (name, is_system) VALUES (?, 0)", (name,))

    logger.debug(f"Added '{name}' to '{table}'.")


def rename_lookup_option(kind: LookupKind, old_name: str, new_name: str) -> None:
    """Renames an entry in a lookup list, cascading the change to every yearly database.

    Args:
        kind (`:enum:LookupKind`): Which lookup list to rename within.
        old_name (str): The entry's current name.
        new_name (str): The entry's new name.

    Raises:
        ValueError: If `old_name` is a system-reserved entry, `new_name` is blank, or an entry
            named `new_name` (case-insensitively) already exists.
    """
    logger.info("Called 'rename_lookup_option'")

    new_name = new_name.strip()
    if not new_name:
        raise ValueError("The name cannot be blank.")

    table = _LOOKUP_TABLE[kind]
    with sq.connect(get_config_db_path()) as connection:
        row = connection.execute(f"SELECT is_system FROM {table} WHERE name = ?", (old_name,)).fetchone()
        if row is not None and bool(row[0]):
            raise ValueError(f"'{old_name}' is required by the app and cannot be renamed.")

        existing = {r[0].lower() for r in connection.execute(f"SELECT name FROM {table} WHERE name != ?", (old_name,))}
        if new_name.lower() in existing:
            raise ValueError(f"'{new_name}' already exists.")

        connection.execute(f"UPDATE {table} SET name = ? WHERE name = ?", (new_name, old_name))

    domain_table, column = _LOOKUP_REFERENCES[kind]
    for year, profile in list_year_profile_pairs():
        with sq.connect(get_db_path(DbLocation(year, profile))) as connection:
            try:
                connection.execute(f"UPDATE {domain_table} SET {column} = ? WHERE {column} = ?", (new_name, old_name))
            except sq.OperationalError:
                continue

    logger.debug(f"Renamed '{old_name}' to '{new_name}' in '{table}' and cascaded across every yearly database.")


def is_lookup_option_in_use(kind: LookupKind, name: str) -> bool:
    """Whether any yearly database has a row referencing `name`.

    Args:
        kind (`:enum:LookupKind`): Which lookup list `name` belongs to.
        name (str): The entry to check.

    Returns:
        bool: `True` if at least one yearly database has a matching row.
    """
    domain_table, column = _LOOKUP_REFERENCES[kind]

    for year, profile in list_year_profile_pairs():
        with sq.connect(get_db_path(DbLocation(year, profile))) as connection:
            try:
                count = connection.execute(
                    f"SELECT COUNT(*) FROM {domain_table} WHERE {column} = ?", (name,)
                ).fetchone()[0]
            except sq.OperationalError:
                continue
            if count > 0:
                return True

    return False


def delete_lookup_option(kind: LookupKind, name: str) -> bool:
    """Deletes an entry from a lookup list, if it's safe to do so.

    Args:
        kind (`:enum:LookupKind`): Which lookup list to delete from.
        name (str): The entry to delete.

    Returns:
        bool: `True` if the entry was deleted; `False` if it's a system-reserved entry or is
            still referenced by at least one yearly database.
    """
    logger.info("Called 'delete_lookup_option'")

    table = _LOOKUP_TABLE[kind]
    with sq.connect(get_config_db_path()) as connection:
        row = connection.execute(f"SELECT is_system FROM {table} WHERE name = ?", (name,)).fetchone()
        if row is not None and bool(row[0]):
            return False

        if is_lookup_option_in_use(kind, name):
            return False

        connection.execute(f"DELETE FROM {table} WHERE name = ?", (name,))

    logger.debug(f"Deleted '{name}' from '{table}'.")
    return True


def fetch_categories() -> list[str]:
    """Fetches every category's display name, sorted alphabetically."""
    return [option.name for option in fetch_lookup_options(LookupKind.CATEGORIES)]


def fetch_sources() -> list[str]:
    """Fetches every source's display name, sorted alphabetically."""
    return [option.name for option in fetch_lookup_options(LookupKind.SOURCES)]


def fetch_kinds() -> list[str]:
    """Fetches every kind's display name, sorted alphabetically."""
    return [option.name for option in fetch_lookup_options(LookupKind.KINDS)]


def get_theme_preference() -> str:
    """Returns the persisted theme mode ("light" or "dark"), defaulting to "light" if unset."""
    logger.info("Called 'get_theme_preference'")

    with sq.connect(get_config_db_path()) as connection:
        row = connection.execute("SELECT value FROM preferences WHERE key = 'theme'").fetchone()

    return row[0] if row is not None else "light"


def set_theme_preference(mode: str) -> None:
    """Persists the theme mode.

    Args:
        mode (str): The theme mode to persist ("light" or "dark").
    """
    logger.info("Called 'set_theme_preference'")

    with sq.connect(get_config_db_path()) as connection:
        connection.execute("INSERT OR REPLACE INTO preferences (key, value) VALUES ('theme', ?)", (mode,))


def get_last_selection() -> tuple[int, str] | None:
    """Returns the last year/profile the welcome page was started with, if any.

    Returns:
        tuple[int, str] | None: The `(year, profile)` last used to start the app, or `None` if
            the app has never been started yet.
    """
    logger.info("Called 'get_last_selection'")

    with sq.connect(get_config_db_path()) as connection:
        rows = dict(connection.execute("SELECT key, value FROM preferences WHERE key IN ('last_year', 'last_profile')"))

    if "last_year" not in rows or "last_profile" not in rows:
        return None

    return int(rows["last_year"]), rows["last_profile"]


def set_last_selection(year: int, profile: str) -> None:
    """Persists the year/profile the welcome page was just started with.

    Args:
        year (int): The year that was selected.
        profile (str): The profile that was selected.
    """
    logger.info("Called 'set_last_selection'")

    with sq.connect(get_config_db_path()) as connection:
        connection.execute("INSERT OR REPLACE INTO preferences (key, value) VALUES ('last_year', ?)", (str(year),))
        connection.execute("INSERT OR REPLACE INTO preferences (key, value) VALUES ('last_profile', ?)", (profile,))
