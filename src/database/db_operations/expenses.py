"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from collections.abc import Generator
from dataclasses import dataclass, field
from logging import getLogger

import numpy as np
from flet import Alignment, Container, DataCell, Text

from helpers.constants import EXPENSES_DB_NAME

from ..data_structures import Categories, Expense
from .utils import WhichDb, get_db_path

__all__ = [
    "SortingConfig",
    "edit_expense",
    "fetch_expenses",
    "fetch_category",
]

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

    with sq.connect(get_db_path(year, WhichDb.EXPENSES)) as connection:
        cursor = connection.cursor()

        # construct command based on differences
        sql_command = [f"{name} = ?" for name in differences.keys()]
        sql_command = "SET " + ", ".join(sql_command)
        sql_params = tuple([val for val in differences.values()]) + (expense_id,)

        cursor.execute(f"UPDATE {EXPENSES_DB_NAME} {sql_command} WHERE id = ?", sql_params)

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
    with sq.connect(get_db_path(year, WhichDb.EXPENSES)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        if month is None and sort is not None:
            cursor.execute(f"SELECT * FROM {EXPENSES_DB_NAME} ORDER BY {sort.sql_command}")
        elif sort is None and month is not None:
            cursor.execute(f"SELECT * FROM {EXPENSES_DB_NAME} WHERE month = ?", (month,))
        elif sort is not None and month is not None:
            cursor.execute(f"SELECT * FROM {EXPENSES_DB_NAME} WHERE month = ? ORDER BY {sort.sql_command}", (month,))
        else:
            cursor.execute(f"SELECT * FROM {EXPENSES_DB_NAME}")

        rows = cursor.fetchall()

        for row in rows:
            yield (row["id"], Expense.get_table_row(row))


def fetch_category(year: int, category: Categories) -> np.ndarray:
    """Fetch the total expense per month for a specified category.

    Args:
        year (int): The year of the expenses.
        category (Categories): The desired category (see `:enum:Categories`).

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_category'")

    with sq.connect(get_db_path(year, WhichDb.EXPENSES)) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT month, SUM(cost) FROM {EXPENSES_DB_NAME} 
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
