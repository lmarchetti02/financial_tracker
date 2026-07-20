"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

import numpy as np

from _helpers.constants import EXPENSES_DB_NAME

from ..data_structures import Categories, Expense
from .generic import get_db_path
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


def fetch_expenses(
    year: int, sort: ESC | None = None, month: int | None = None, category: Categories | None = None
) -> RowGenerator:
    """Fetches all the expenses.

    Args:
        year (int): The year of the expenses in the database.
        sort (ExpensesSortingConfig | None): If given, the rows gets sorted (see `ExpensesSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.
        category (Categories | None): The category to filter the table by. See `:enum:Categories`.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the expense in the database.
    """
    with sq.connect(get_db_path(year)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        conditions: list[str] = []
        params: list[int | str] = []
        if month is not None:
            conditions.append("month = ?")
            params.append(month)
        if category is not None:
            conditions.append("category = ?")
            params.append(category.name)

        query = f"SELECT * FROM {EXPENSES_DB_NAME}"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if sort is not None:
            query += f" ORDER BY {sort.sql_command}"

        cursor.execute(query, params)

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

    with sq.connect(get_db_path(year)) as connection:
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
