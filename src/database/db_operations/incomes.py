"""Implementation of the main operations on the incomes database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

import numpy as np

from _helpers.constants import INCOME_DB_NAME

from ..data_structures import Income, Sources
from .generic import get_db_path
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class IncomesSortingConfig(SortingConfig):
    """Defines how the expenses are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
        if self.ascending:
            order = "ASC"
        else:
            order = "DESC"

        if self.col_id == 0:
            self.sql_command = f"month {order}"
        elif self.col_id == 2:
            self.sql_command = f"amount {order}"
        else:
            raise ValueError("You cannot sort this column.")


type ISC = IncomesSortingConfig


def fetch_incomes(
    year: int, sort: ISC | None = None, month: int | None = None, source: Sources | None = None
) -> RowGenerator:
    """Fetches all the incomes.

    Args:
        year (int): The year of the expenses in the database.
        sort (IncomesSortingConfig | None): If given, the rows gets sorted (see `IncomesSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.
        source (Sources | None): The source to filter the table by. See `:enum:Sources`.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the incomes in the database.
    """
    logger.info("Called 'fetch_incomes'")
    with sq.connect(get_db_path(year)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        conditions: list[str] = []
        params: list[int | str] = []
        if month is not None:
            conditions.append("month = ?")
            params.append(month)
        if source is not None:
            conditions.append("source = ?")
            params.append(source.name)

        query = f"SELECT * FROM {INCOME_DB_NAME}"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if sort is not None:
            query += f" ORDER BY {sort.sql_command}"

        cursor.execute(query, params)

        rows = cursor.fetchall()

        for row in rows:
            yield (row["id"], Income.get_table_row(row))


def fetch_source(year: int, source: Sources) -> np.ndarray:
    """Fetch the total income per month for a specified source.

    Args:
        year (int): The year of the incomes.
        source (Sources): The desired source (see `:enum:Sources`).

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_source'")

    with sq.connect(get_db_path(year)) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT month, SUM(amount) FROM {INCOME_DB_NAME}
            WHERE source = ?
            GROUP BY month
            ORDER BY month ASC
            """,
            (source.name,),
        )

        monthly_total = np.zeros(12, dtype=np.float32)
        for row in cursor.fetchall():
            monthly_total[row[0] - 1] = row[1]

        return monthly_total
