"""Implementation of the main operations on the transfers database."""

import sqlite3 as sq
from dataclasses import dataclass
from logging import getLogger

from _helpers.constants import TRANSFERS_DB_NAME

from ..data_structures import Transfer
from .generic import DbLocation, fetch_rows, get_db_path
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class TransfersSortingConfig(SortingConfig):
    """Defines how the transfers are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
        self._resolve({0: "month", 6: "amount"})


type TSC = TransfersSortingConfig


def fetch_transfers(
    location: DbLocation,
    sort: TSC | None = None,
    month: int | None = None,
    kind: str | None = None,
) -> RowGenerator:
    """Fetches all the transfers.

    Args:
        location (`:class:DbLocation`): The year/profile of the transfers in the database.
        sort (TransfersSortingConfig | None): If given, the rows gets sorted (see `TransfersSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.
        kind (str | None): The kind to filter the table by.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the transfers in the database.
    """
    logger.info("Called 'fetch_transfers'")
    extra_filter = ("kind", kind) if kind is not None else None
    return fetch_rows(location, TRANSFERS_DB_NAME, Transfer, sort=sort, month=month, extra_filter=extra_filter)


def fetch_fee_expense_ids(location: DbLocation) -> set[int]:
    """Fetches the ids of every `:class:Expense` currently linked to a transfer's fee.

    Args:
        location (`:class:DbLocation`): The year/profile of the transfers in the database.

    Returns:
        set[int]: The ids of the `:class:Expense` rows referenced by some transfer's `fee_expense_id`.
    """
    logger.info("Called 'fetch_fee_expense_ids'")

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"SELECT fee_expense_id FROM {TRANSFERS_DB_NAME} WHERE fee_expense_id IS NOT NULL")
        return {row[0] for row in cursor.fetchall()}


def fetch_profit_income_ids(location: DbLocation) -> set[int]:
    """Fetches the ids of every `:class:Income` currently linked to a transfer's profit.

    Args:
        location (`:class:DbLocation`): The year/profile of the transfers in the database.

    Returns:
        set[int]: The ids of the `:class:Income` rows referenced by some transfer's `profit_income_id`.
    """
    logger.info("Called 'fetch_profit_income_ids'")

    with sq.connect(get_db_path(location)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"SELECT profit_income_id FROM {TRANSFERS_DB_NAME} WHERE profit_income_id IS NOT NULL")
        return {row[0] for row in cursor.fetchall()}
