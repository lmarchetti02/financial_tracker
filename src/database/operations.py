"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from collections.abc import Generator
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path

import numpy as np
from flet import Alignment, Container, DataCell, Text

from helpers.constants import DB_DIRECTORY, DB_NAME

from .expense import Categories, Expense

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


def get_db_path(year: int) -> Path:
    """Returns the path to the expenses database for the current year."""
    return Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db")


def initialize_db(year: int) -> None:
    """Initializes the database if it doesn't already exist.

    Args:
        year (int): The year of the expenses in the database.
    """
    logger.info("Called 'initialize_db'.")

    # create necessary dir
    DB_DIRECTORY.mkdir(parents=True, exist_ok=True)
    db_path = get_db_path(year)
    logger.debug("Created database dir if it didn't already exist.")

    # create database
    with sq.connect(db_path) as connection:
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

    with sq.connect(get_db_path(year)) as connection:
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


def remove_expense(year: int, expense_id: int) -> bool:
    """Deletes an expense from the database.

    Args:
        year (int): The year of the expenses in the database.
        expense_id (int): The id of the expense to delete.

    Returns:
        bool: `True` if the operation succeeded, `False` if it didn't.
    """
    logger.info("Called 'remove_expense'")

    with sq.connect(get_db_path(year)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {DB_NAME} WHERE id = ? RETURNING *", (expense_id,))

        deleted_expense = cursor.fetchone()
        logger.debug(f"Deleted expense:\n{deleted_expense}")

        return cursor.rowcount > 0


def edit_expense(year: int, expense_id: int, old: Expense, new: Expense) -> bool:
    """Edits an expense in the database.

    Args:
        year (int): The year of the expenses in the database.
        expense_id (int): The id of the expense to edit.
        old (Expense): The expense to modify.
        new (Expense): The modified expense.

    Returns:
        bool: `True` if the operation succeeded, `False` if it didn't.
    """
    logger.info("Called 'edit_expense'")

    # get differences between old and new
    differences = old - new
    if "category" in differences:
        differences["category"] = differences["category"].name
    logger.debug(f"Differences:\n{differences}")

    with sq.connect(get_db_path(year)) as connection:
        cursor = connection.cursor()

        # construct command based on differences
        sql_command = [f"{name} = ?" for name in differences.keys()]
        sql_command = "SET " + ", ".join(sql_command)
        sql_params = tuple([val for val in differences.values()]) + (expense_id,)

        cursor.execute(f"UPDATE {DB_NAME} {sql_command} WHERE id = ?", sql_params)

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
    with sq.connect(get_db_path(year)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        if month is None and sort is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} ORDER BY {sort.sql_command}")
        elif sort is None and month is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} WHERE month = ?", (month,))
        elif sort is not None and month is not None:
            cursor.execute(f"SELECT * FROM {DB_NAME} WHERE month = ? ORDER BY {sort.sql_command}", (month,))
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
                    DataCell(Container(Text(str(row["month"])), alignment=Alignment.CENTER)),
                    DataCell(Container(Text(days), alignment=Alignment.CENTER)),
                    DataCell(Text(str(row["description"]))),
                    DataCell(Text(str(row["category"]).lower().capitalize().replace("_", " "))),
                    DataCell(Text(f"{row['cost']:.2f}")),
                ],
            )


def fetch_category(year: int, category: Categories) -> np.ndarray:
    """Fetch the total expense per month for a specified category.

    Args:
        year (int): The year of the expenses.
        category (Categories): The desired category (see `:enum:Categories`).

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_category'")

    with sq.connect(get_db_path(year)) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT month, SUM(cost) FROM {DB_NAME} 
            WHERE category = ?
            GROUP BY month
            ORDER BY month ASC
            """,
            (category.name,),
        )

        monthly_total = np.zeros(12, dtype=np.float32)
        for row in cursor.fetchall():
            monthly_total[row[0] - 1] = row[1]

        return monthly_total


def fetch_by_id(year: int, expense_id: int) -> Expense:
    """Fetches the expense with the desired ID.

    Args:
        year (int): The year of the expenses in the database.
        expense_id (int): The id of the expense to delete.

    Returns:
        Expense: The desired expense.
    """
    logger.info("Called 'fetch_by_id'")

    with sq.connect(get_db_path(year)) as connection:
        cursor = connection.cursor()

        cursor.execute(f"SELECT * FROM {DB_NAME} WHERE id = ?", (expense_id,))
        fields = cursor.fetchone()

        expense = Expense.init_from_tuple(fields[1:])
        logger.debug(f"Expense retrieved by ID:\n{expense}")

        return expense
