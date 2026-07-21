"""Implementation of the main operations on the incomes database."""

from dataclasses import dataclass
from logging import getLogger

import numpy as np

from _helpers.constants import INCOME_DB_NAME

from ..data_structures import Income, Sources
from .generic import fetch_monthly_totals, fetch_rows
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class IncomesSortingConfig(SortingConfig):
    """Defines how the expenses are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
        self._resolve({0: "month", 3: "amount"})


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
    extra_filter = ("source", source) if source is not None else None
    return fetch_rows(year, INCOME_DB_NAME, Income, sort=sort, month=month, extra_filter=extra_filter)


def fetch_source(year: int, source: Sources) -> np.ndarray:
    """Fetch the total income per month for a specified source.

    Args:
        year (int): The year of the incomes.
        source (Sources): The desired source (see `:enum:Sources`).

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_source'")

    return fetch_monthly_totals(year, INCOME_DB_NAME, "amount", "source", source)


def fetch_income_totals(year: int) -> np.ndarray:
    """Fetch the total income per month across all sources.

    Args:
        year (int): The year of the incomes.

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_income_totals'")

    return fetch_monthly_totals(year, INCOME_DB_NAME, "amount")
