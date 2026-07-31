"""Some helper functions."""

import re
import sqlite3 as sq
from dataclasses import dataclass, fields
from enum import Enum, auto
from logging import getLogger
from pathlib import Path
from typing import Literal, overload

import numpy as np

from _helpers.constants import APP_DIRECTORY, DEFAULT_PROFILE_NAME

from ..data_structures import (Account, AccountBalance, DataContainer, Expense,
                               Holding, HoldingKindTarget,
                               HoldingRegionAllocation, Income, Transfer)
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


class WhichDb(Enum):
    """Defines the database to use."""

    EXPENSES = auto()
    INCOMES = auto()
    TRANSFERS = auto()
    ACCOUNTS = auto()
    ACCOUNT_BALANCES = auto()
    HOLDINGS = auto()
    HOLDING_REGION_ALLOCATIONS = auto()
    HOLDING_KIND_TARGETS = auto()


_DB_TO_CLASS = {
    WhichDb.EXPENSES: Expense,
    WhichDb.INCOMES: Income,
    WhichDb.TRANSFERS: Transfer,
    WhichDb.ACCOUNTS: Account,
    WhichDb.ACCOUNT_BALANCES: AccountBalance,
    WhichDb.HOLDINGS: Holding,
    WhichDb.HOLDING_REGION_ALLOCATIONS: HoldingRegionAllocation,
    WhichDb.HOLDING_KIND_TARGETS: HoldingKindTarget,
}
_CLASS_TO_DB = {
    Expense: WhichDb.EXPENSES,
    Income: WhichDb.INCOMES,
    Transfer: WhichDb.TRANSFERS,
    Account: WhichDb.ACCOUNTS,
    AccountBalance: WhichDb.ACCOUNT_BALANCES,
    Holding: WhichDb.HOLDINGS,
    HoldingRegionAllocation: WhichDb.HOLDING_REGION_ALLOCATIONS,
    HoldingKindTarget: WhichDb.HOLDING_KIND_TARGETS,
}


@dataclass(frozen=True)
class DbLocation:
    """Identifies which year/profile's SQLite database file to use.

    Attributes:
        year (int): The desired year.
        profile (str): The desired profile (e.g. distinct datasets for the same year, like a
            personal and a shared tracker). Defaults to `:const:DEFAULT_PROFILE_NAME`.
    """

    year: int
    profile: str = DEFAULT_PROFILE_NAME


def get_db_path(location: DbLocation) -> Path:
    """Returns the path to the shared database file for the given year and profile.

    Args:
        location (`:class:DbLocation`): The year/profile whose database file to locate.

    Returns:
        Path: The path to the database file for `location`.
    """
    return APP_DIRECTORY / f"{location.year}_{location.profile}_data.db"


_DB_PATTERN = re.compile(r"^(\d+)_(.+)_data$")


def list_year_profile_pairs() -> list[tuple[int, str]]:
    """Lists every `(year, profile)` pair that has an existing database file.

    Returns:
        list[tuple[int, str]]: The `(year, profile)` pairs found under `APP_DIRECTORY`.
    """
    if not APP_DIRECTORY.is_dir():
        return []

    pairs = []
    for path in APP_DIRECTORY.glob("*_data.db"):
        match = _DB_PATTERN.match(path.stem)
        if match is None:
            continue
        pairs.append((int(match.group(1)), match.group(2)))

    return pairs


def fetch_rows(
    location: DbLocation,
    table_name: str,
    target_cls: type[DataContainer],
    sort: SortingConfig | None = None,
    month: int | None = None,
    extra_filter: tuple[str, str] | None = None,
) -> RowGenerator:
    """Fetches all the rows of a domain table, optionally filtered and sorted.

    Args:
        location (`:class:DbLocation`): The year/profile of the database to query.
        table_name (str): The name of the table to query.
        target_cls (type[`:class:DataContainer`]): The class whose `get_table_row` renders each row.
        sort (`:class:SortingConfig` | None): If given, the rows get sorted accordingly.
            Defaults to `None`.
        month (int | None): The month to filter the table by. Defaults to `None`.
        extra_filter (tuple[str, str] | None): An optional `(column_name, value)` pair used
            as an additional equality filter. Defaults to `None`.

    Returns:
        RowGenerator: The generator that yields the rows and the id of each item in the database.
    """
    with sq.connect(get_db_path(location)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        conditions: list[str] = []
        params: list[int | str] = []
        if month is not None:
            conditions.append("month = ?")
            params.append(month)
        if extra_filter is not None:
            column_name, value = extra_filter
            conditions.append(f"{column_name} = ?")
            params.append(value)

        query = f"SELECT * FROM {table_name}"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if sort is not None:
            query += f" ORDER BY {sort.sql_command}"

        cursor.execute(query, params)

        for row in cursor.fetchall():
            yield (row["id"], target_cls.get_table_row(row))


def fetch_monthly_totals(
    location: DbLocation,
    table_name: str,
    sum_column: str,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> np.ndarray:
    """Fetches the per-month total of a numeric column, optionally filtered by one column.

    Args:
        location (`:class:DbLocation`): The year/profile of the database to query.
        table_name (str): The name of the table to query.
        sum_column (str): The numeric column to sum.
        filter_column (str | None): The column to filter by. If omitted, the column is
            summed across the whole table. Defaults to `None`.
        filter_value (str | None): The value to filter `filter_column` by. Defaults to `None`.

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_monthly_totals'")

    where_clause = f"WHERE {filter_column} = ?" if filter_column is not None else ""
    params = (filter_value,) if filter_value is not None else ()

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT month, SUM({sum_column}) FROM {table_name}
            {where_clause}
            GROUP BY month
            ORDER BY month ASC
            """,
            params,
        )

        monthly_total = np.zeros(12, dtype=np.float32)
        for row in cursor.fetchall():
            monthly_total[row[0] - 1] = row[1]

        return monthly_total


def initialize_db(location: DbLocation, db: WhichDb) -> None:
    """Initializes the database if it doesn't already exist.

    Args:
        location (`:class:DbLocation`): The year/profile to initialize.
        db (`:enum:WhichDb`): The db to initialize.
    """
    logger.info(f"Called 'initialize_db' for {db}.")

    # create database
    db_path = get_db_path(location)
    with sq.connect(db_path) as connection:
        # create cursor
        cursor = connection.cursor()

        # create table
        cursor.execute(_DB_TO_CLASS[db].create_table())

        # backfill any columns added to the dataclass since the table was created
        _DB_TO_CLASS[db].add_missing_columns(cursor)

        # create index on categories for more efficient filtering
        db_name = _DB_TO_CLASS[db].db_name
        if db not in (
            WhichDb.ACCOUNTS,
            WhichDb.HOLDINGS,
            WhichDb.HOLDING_REGION_ALLOCATIONS,
            WhichDb.HOLDING_KIND_TARGETS,
        ):
            # `Account`/`Holding`/`HoldingRegionAllocation`/`HoldingKindTarget` have no `month` column,
            # unlike every other domain
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_month ON {db_name}(month)")
        if db == WhichDb.EXPENSES:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_category ON {db_name}(category)")
        elif db == WhichDb.INCOMES:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_source ON {db_name}(source)")
        elif db == WhichDb.TRANSFERS:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_kind ON {db_name}(kind)")
        elif db == WhichDb.ACCOUNT_BALANCES:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_account_id ON {db_name}(account_id)")
        elif db == WhichDb.HOLDING_REGION_ALLOCATIONS:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_holding_id ON {db_name}(holding_id)")

        logger.debug(f"Created table '{db_name}' inside {db_path} if it didn't already exist.")


@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.EXPENSES], row_id: int) -> Expense: ...
@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.INCOMES], row_id: int) -> Income: ...
@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.TRANSFERS], row_id: int) -> Transfer: ...
@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.ACCOUNTS], row_id: int) -> Account: ...
@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.ACCOUNT_BALANCES], row_id: int) -> AccountBalance: ...
@overload
def fetch_by_id(location: DbLocation, db: Literal[WhichDb.HOLDINGS], row_id: int) -> Holding: ...
@overload
def fetch_by_id(
    location: DbLocation, db: Literal[WhichDb.HOLDING_REGION_ALLOCATIONS], row_id: int
) -> HoldingRegionAllocation: ...
def fetch_by_id(location: DbLocation, db: WhichDb, row_id: int) -> DataContainer:
    """Fetches the expense with the desired ID.

    Args:
        location (`:class:DbLocation`): The year/profile of the database to query.
        db (`:enum:WhichDb`): The db to use.
        row_id (int): The id of the row to fetch.

    Returns:
        `:class:DataContainer`: The desired object.

    Raises:
        ValueError: If no row with `row_id` exists in the given db.
    """
    logger.info("Called 'fetch_by_id'")

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()

        cursor.execute(f"SELECT * FROM {_DB_TO_CLASS.get(db).db_name} WHERE id = ?", (row_id,))  # type: ignore
        fields = cursor.fetchone()

        if fields is None:
            raise ValueError(f"No item with id {row_id} found in '{_DB_TO_CLASS[db].db_name}'.")

        if db == WhichDb.EXPENSES:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.INCOMES:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.TRANSFERS:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.ACCOUNTS:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.ACCOUNT_BALANCES:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.HOLDINGS:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.HOLDING_REGION_ALLOCATIONS:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        logger.debug(f"Object retrieved by ID:\n{data}")

        return data


def add_item(location: DbLocation, item: DataContainer) -> int:
    """Adds a `:class:DataContainer` subclass instance to the database.

    Args:
        location (`:class:DbLocation`): The desired year/profile.
        item (`:class:DataContainer`): The item to add.

    Returns:
        int: The id of the newly inserted row.
    """
    logger.info("Called 'add_item'.")

    db_enum = _CLASS_TO_DB.get(type(item))
    if not db_enum:
        raise ValueError(f"Unsupported item type: {type(item)}")

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()

        # get names and values
        columns = []
        values = []
        for f in fields(item):
            columns.append(f.name)
            val = getattr(item, f.name)

            if isinstance(val, Enum):
                values.append(val.name)
            else:
                values.append(val)

        # generate sql query
        col_str = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        query = f"INSERT INTO {item.db_name} ({col_str}) VALUES ({placeholders})"

        cursor.execute(query, tuple(values))
        logger.debug(f"Added item to the database:\n{item}.")

        return cursor.lastrowid


def remove_item(location: DbLocation, db: WhichDb, row_id: int) -> bool:
    """Removes a `:class:DataContainer` subclass instance from the database.

    Args:
        location (`:class:DbLocation`): The desired year/profile.
        db (`:enum:WhichDb`): The db to use.
        row_id (int): The ID of the row where the item is stored.

    Returns:
        `True` if the operation was successful, `False` otherwise.
    """
    logger.info("Called 'remove_expense'")

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {_DB_TO_CLASS.get(db).db_name} WHERE id = ? RETURNING *", (row_id,))  # type: ignore

        deleted_item = cursor.fetchone()
        logger.debug(f"Deleted item:\n{deleted_item}")

        return cursor.rowcount > 0


def edit_item(location: DbLocation, row_id: int, old: DataContainer, new: DataContainer) -> bool:
    """Edits an item in the database.

    Args:
        location (`:class:DbLocation`): The desired year/profile.
        row_id (int): The ID of the row where the item is stored.
        old (`:class:DataContainer`): The item to modify.
        new (`:class:DataContainer`): The modified item.

    Returns:
        bool: `True` if the operation succeeded (including a no-op edit where nothing
            differed between `old` and `new`), `False` if it didn't.
    """
    logger.info("Called 'edit_expense'")

    if type(old) is not type(new):
        raise ValueError("New and old item must be of the same type.")

    db_enum = _CLASS_TO_DB.get(type(old))
    if not db_enum:
        raise ValueError(f"Unsupported item type: {type(old)}")

    # get differences between old and new
    differences = old - new
    logger.debug(f"Differences:\n{differences}")

    if not differences:
        logger.debug("No differences between old and new; nothing to update.")
        return True

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()

        # construct command based on differences
        sql_command = [f"{name} = ?" for name in differences.keys()]
        sql_command = "SET " + ", ".join(sql_command)
        sql_params = tuple([val for val in differences.values()]) + (row_id,)

        cursor.execute(f"UPDATE {_DB_TO_CLASS[db_enum].db_name} {sql_command} WHERE id = ?", sql_params)

        return cursor.rowcount > 0
