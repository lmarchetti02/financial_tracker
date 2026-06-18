"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from collections.abc import Generator
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path

from flet import DataCell, Text

from helpers.constants import DB_DIRECTORY, DB_NAME

from .expense import Expense

logger = getLogger("financial_tracker")

type RowGenerator = Generator[tuple[int, list[DataCell]], None, None]


@dataclass
class SortingConfig:
    """Helper class to properly sort columns.

    Attributes:
        col_id (int): The ID of the column given by flet.
        ascending (int): Whether the column is to be sorted in ascending
            (`True`) or descending (`False`) order.
        sql_command (str): The sqlite command that corresponds to the given
            `col_id` and `ascending`.

    Raises:
        ValueError: If the column is not sortable.
    """

    col_id: int
    ascending: bool

    sql_command: str = field(init=False)

    def __post_init__(self) -> None:
        """Converts the attributes given by flet to strings that can be passed to sqlite."""
        if self.ascending:
            order = "ASC"
        else:
            order = "DESC"

        if self.col_id == 0:
            self.sql_command = f"month {order}, day_start {order}"
        elif self.col_id == 4:
            self.sql_command = f"cost {order}"
        else:
            raise ValueError("You cannot sort this column.")


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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_month ON expenses(month)")
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


def fetch_expenses(year: int, sort: SortingConfig | None = None, month: int | None = None) -> RowGenerator:
    """Fetches all the expenses.

    Args:
        year (int): The year of the expenses in the database.
        sort (SortingConfig | None): If given, the rows gets sorted (see `SortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the expense in the database.
    """
    with sq.connect(str(Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db"))) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        if month is None and sort is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} ORDER BY {sort.sql_command}")
        elif sort is None and month is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} WHERE month = ?", str(month))
        elif sort is not None and month is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} WHERE month = ? ORDER BY {sort.sql_command}", str(month))
        else:
            cursor.execute(f"SELECT * FROM {DB_NAME}")

        rows = cursor.fetchall()

        for row in rows:
            if row["day_end"] is not None:
                days = f"{row['day_start']}-{row['day_end']}"
            else:
                days = str(row["day_start"])
            yield (
                # TODO: Move it to expense.py
                row["id"],
                [
                    DataCell(Text(str(row["month"]))),
                    DataCell(Text(days)),
                    DataCell(Text(str(row["description"]))),
                    DataCell(Text(str(row["category"]).lower().capitalize().replace("_", " "))),
                    DataCell(Text(str(row["cost"]))),
                ],
            )
