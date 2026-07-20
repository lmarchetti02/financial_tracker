"""Implementation of the main operations on the transfers database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

from helpers.constants import TRANSFERS_DB_NAME

from ..data_structures import Transfer
from .generic import WhichDb, get_db_path
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
        elif self.col_id == 5:
            self.sql_command = f"amount {order}"
        else:
            raise ValueError("You cannot sort this column.")


type TSC = TransfersSortingConfig


def fetch_transfers(year: int, sort: TSC | None = None, month: int | None = None) -> RowGenerator:
    """Fetches all the transfers.

    Args:
        year (int): The year of the transfers in the database.
        sort (TransfersSortingConfig | None): If given, the rows gets sorted (see `TransfersSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the transfers in the database.
    """
    logger.info("Called 'fetch_transfers'")
    with sq.connect(get_db_path(year, WhichDb.TRANSFERS)) as connection:
        # enable column access by name
        connection.row_factory = sq.Row
        cursor = connection.cursor()

        if month is None and sort is not None:
            cursor.execute(f"SELECT * FROM {TRANSFERS_DB_NAME} ORDER BY {sort.sql_command}")
        elif sort is None and month is not None:
            cursor.execute(f"SELECT * FROM {TRANSFERS_DB_NAME} WHERE month = ?", (month,))
        elif sort is not None and month is not None:
            cursor.execute(f"SELECT * FROM {TRANSFERS_DB_NAME} WHERE month = ? ORDER BY {sort.sql_command}", (month,))
        else:
            cursor.execute(f"SELECT * FROM {TRANSFERS_DB_NAME}")

        rows = cursor.fetchall()

        for row in rows:
            yield (row["id"], Transfer.get_table_row(row))
