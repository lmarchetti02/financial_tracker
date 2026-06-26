"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

import numpy as np

from helpers.constants import EXPENSES_DB_NAME

from ..data_structures import Categories, Expense
from .generic import WhichDb, get_db_path
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class ExpensesSortingConfig(SortingConfig):
    """Defines how the expenses are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
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


type ESC = ExpensesSortingConfig


def fetch_expenses(year: int, sort: ESC | None = None, month: int | None = None) -> RowGenerator:
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
