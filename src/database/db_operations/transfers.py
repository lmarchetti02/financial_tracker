"""Implementation of the main operations on the transfers database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

from _helpers.constants import TRANSFERS_DB_NAME

from ..data_structures import Kind, Transfer
from .generic import get_db_path
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class TransfersSortingConfig(SortingConfig):
    """Defines how the transfers are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
        if self.ascending:
            order = "ASC"
        else:
            order = "DESC"

        if self.col_id == 0:
            self.sql_command = f"month {order}"
        elif self.col_id == 6:
            self.sql_command = f"amount {order}"
        else:
            raise ValueError("You cannot sort this column.")


type TSC = TransfersSortingConfig


def fetch_transfers(
    year: int, sort: TSC | None = None, month: int | None = None, kind: Kind | None = None
) -> RowGenerator:
    """Fetches all the transfers.

    Args:
        year (int): The year of the transfers in the database.
        sort (TransfersSortingConfig | None): If given, the rows gets sorted (see `TransfersSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.
        kind (Kind | None): The kind to filter the table by. See `:enum:Kind`.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the transfers in the database.
    """
    logger.info("Called 'fetch_transfers'")
    with sq.connect(get_db_path(year)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        conditions: list[str] = []
        params: list[int | str] = []
        if month is not None:
            conditions.append("month = ?")
            params.append(month)
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind.name)

        query = f"SELECT * FROM {TRANSFERS_DB_NAME}"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if sort is not None:
            query += f" ORDER BY {sort.sql_command}"

        cursor.execute(query, params)

        rows = cursor.fetchall()

        for row in rows:
            yield (row["id"], Transfer.get_table_row(row))
