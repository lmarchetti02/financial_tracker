"""Some helper functions."""

import sqlite3 as sq
from dataclasses import fields
from enum import Enum, auto
from logging import getLogger
from pathlib import Path
from typing import Literal, overload

from helpers.constants import APP_DIRECTORY

from ..data_structures import DataContainer, Expense, Income

logger = getLogger("financial_tracker")


class WhichDb(Enum):
    """Defines the database to use."""

    EXPENSES = auto()
    INCOMES = auto()


_DB_TO_CLASS = {WhichDb.EXPENSES: Expense, WhichDb.INCOMES: Income}
_CLASS_TO_DB = {Expense: WhichDb.EXPENSES, Income: WhichDb.INCOMES}


def get_db_path(year: int, db: WhichDb) -> Path:
    """Returns the path to the desired database for the current year.

    Args:
        year (int): The desired year.
        db (`:enum:WhichDb`): The db to fetch.

    Returns:
        Path: The path to the desired database.
    """
    return Path.home() / APP_DIRECTORY / f"{year}_data" / (_DB_TO_CLASS[db].db_name + f"_{year}.db")


def initialize_db(year: int, db: WhichDb) -> None:
    """Initializes the database if it doesn't already exist.

    Args:
        year (int): The desired year.
        db (`:enum:WhichDb`): The db to initialize.
    """
    logger.info(f"Called 'initialize_db' for {db}.")

    # create database
    db_path = get_db_path(year, db)
    with sq.connect(db_path) as connection:
        # create cursor
        cursor = connection.cursor()

        # create table
        cursor.execute(_DB_TO_CLASS[db].create_table())

        # create index on categories for more efficient filtering
        db_name = _DB_TO_CLASS[db].db_name
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_month ON {db_name}(month)")
        if db == WhichDb.EXPENSES:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_category ON {db_name}(category)")
        elif db == WhichDb.INCOMES:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_source ON {db_name}(source)")

        logger.debug(f"Created table inside {db_path} if it didn't already exist.")


@overload
def fetch_by_id(year: int, db: Literal[WhichDb.EXPENSES], row_id: int) -> Expense: ...


@overload
def fetch_by_id(year: int, db: Literal[WhichDb.INCOMES], row_id: int) -> Income: ...


def fetch_by_id(year: int, db: WhichDb, row_id: int) -> DataContainer:
    """Fetches the expense with the desired ID.

    Args:
        year (int): The year of the expenses in the database.
        db (`:enum:WhichDb`): The db to use.
        row_id (int): The id of the row to fetch.

    Returns:
        `:class:DataContainer`: The desired object.
    """
    logger.info("Called 'fetch_by_id'")

    with sq.connect(get_db_path(year, db)) as connection:
        cursor = connection.cursor()

        cursor.execute(f"SELECT * FROM {_DB_TO_CLASS.get(db).db_name} WHERE id = ?", (row_id,))  # type: ignore
        fields = cursor.fetchone()

        if db == WhichDb.EXPENSES:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        elif db == WhichDb.INCOMES:
            data = _DB_TO_CLASS.get(db).init_from_tuple(fields[1:])  # type: ignore
        logger.debug(f"Object retrieved by ID:\n{data}")

        return data


def add_item(year: int, item: DataContainer) -> None:
    """Adds a `:class:DataContainer` subclass instance to the database.

    Args:
        year (int): The desired year.
        item (`:class:DataContainer`): The item to add.
    """
    logger.info("Called 'add_item'.")

    db_enum = _CLASS_TO_DB.get(type(item))
    if not db_enum:
        raise ValueError(f"Unsupported item type: {type(item)}")

    with sq.connect(get_db_path(year, db_enum)) as connection:
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


def remove_item(year: int, db: WhichDb, row_id: int) -> bool:
    """Removes a `:class:DataContainer` subclass instance from the database.

    Args:
        year (int): The desired year.
        db (`:enum:WhichDb`): The db to use.
        row_id (int): The ID of the row where the item is stored.

    Returns:
        `True` if the operation was successful, `False` otherwise.
    """
    logger.info("Called 'remove_expense'")

    with sq.connect(get_db_path(year, db)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {_DB_TO_CLASS.get(db).db_name} WHERE id = ? RETURNING *", (row_id,))  # type: ignore

        deleted_item = cursor.fetchone()
        logger.debug(f"Deleted item:\n{deleted_item}")

        return cursor.rowcount > 0


def edit_item(year: int, row_id: int, old: DataContainer, new: DataContainer) -> bool:
    """Edits an item in the database.

    Args:
        year (int): The desired year.
        row_id (int): The ID of the row where the item is stored.
        old (`:class:DataContainer`): The item to modify.
        new (`:class:DataContainer`): The modified item.

    Returns:
        bool: `True` if the operation succeeded, `False` if it didn't.
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

    with sq.connect(get_db_path(year, WhichDb.EXPENSES)) as connection:
        cursor = connection.cursor()

        # construct command based on differences
        sql_command = [f"{name} = ?" for name in differences.keys()]
        sql_command = "SET " + ", ".join(sql_command)
        sql_params = tuple([val for val in differences.values()]) + (row_id,)

        cursor.execute(f"UPDATE {_DB_TO_CLASS[db_enum].db_name} {sql_command} WHERE id = ?", sql_params)

        return cursor.rowcount > 0
