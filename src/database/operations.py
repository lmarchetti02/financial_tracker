"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from collections.abc import Generator
from logging import getLogger
from pathlib import Path

from flet import DataCell, Text

from helpers.constants import DB_DIRECTORY, DB_NAME

from .expense import Expense

logger = getLogger("financial_tracker")


def initialize_db(year: int) -> None:
    """Initializes the database if it doesn't already exist.

    Args:
        year (int): The year of the expenses in the database.
    """
    logger.info("Called 'initialize_db'.")

    # create necessary dir
    app_dir = Path.home() / DB_DIRECTORY
    app_dir.mkdir(parents=True, exist_ok=True)
    db_path = app_dir / (DB_NAME + f"_{year}.db")
    logger.debug("Created database dir if it didn't already exist.")

    # create database
    with sq.connect(str(db_path)) as connection:
        # create cursor
        cursor = connection.cursor()

        # create table
        cursor.execute(Expense.create_table())

        # create index on categories for more efficient filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON expenses(category)")
        logger.debug(f"Created table inside {db_path} if it didn't already exist.")


def add_expense(year: int, expense: Expense) -> None:
    """Adds an expense to the database.

    Args:
        year (int): The year of the expenses in the database.
        expense (Expense): The expense to add.
    """
    logger.info("Called 'add_expense'.")

    with sq.connect(str(Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db"))) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO {DB_NAME} (month, day_start, day_end, description, category, cost)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                expense.month,
                expense.day_start,
                expense.day_end,
                expense.description,
                expense.category.name,
                expense.cost,
            ),
        )
        logger.debug(f"Added expense to the database:\n{expense}.")


def remove_expense(year: int, id: int) -> bool:
    """Deletes an expense from the database.

    Args:
        year (int): The year of the expenses in the database.
        id (int): The id of the expense to delete.

    Returns:
        bool: `True` if the operation succeeded, `False` if it didn't.
    """
    logger.info("Called 'remove_expense'")

    with sq.connect(str(Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db"))) as connection:
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {DB_NAME} WHERE id = ? RETURNING *", (id,))

        deleted_expense = cursor.fetchone()
        logger.debug(f"Deleted expense:\n{deleted_expense}")

        return cursor.rowcount > 0


def fetch_expenses(year: int) -> Generator[list[DataCell], None, None]:
    """Fetches all the expenses.

    Args:
        year (int): The year of the expenses in the database.

    Returns:
        Generator[list[DataCell], None, None]: The generator that yields the rows.
    """
    with sq.connect(str(Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db"))) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        cursor.execute(f"SELECT * FROM {DB_NAME}")
        rows = cursor.fetchall()

        for row in rows:
            if row["day_end"] is not None:
                days = f"{row['day_start']}-{row['day_end']}"
            else:
                days = str(row["day_start"])
            yield [
                DataCell(Text(str(row["month"]))),
                DataCell(Text(days)),
                DataCell(Text(str(row["description"]))),
                DataCell(Text(str(row["category"]))),
                DataCell(Text(str(row["cost"]))),
            ]
