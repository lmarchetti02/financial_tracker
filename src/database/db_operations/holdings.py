"""Implementation of the main operations on the holdings database."""

import sqlite3 as sq
from dataclasses import replace
from datetime import date
from logging import getLogger

from _helpers.constants import (HOLDING_REGION_ALLOCATIONS_DB_NAME,
                                HOLDINGS_DB_NAME)
from _helpers.market_data import fetch_price

from ..data_structures import Holding, HoldingRegionAllocation
from .generic import (DbLocation, WhichDb, add_item, edit_item, get_db_path,
                      remove_item)

logger = getLogger("financial_tracker")


def fetch_holdings(location: DbLocation) -> list[tuple[int, Holding]]:
    """Fetches every holding defined for the year, ordered by kind, then name.

    Args:
        location (`:class:DbLocation`): The year/profile of the holdings in the database.

    Returns:
        list[tuple[int, Holding]]: The id and the reconstructed `:class:Holding` for each row.
    """
    logger.info("Called 'fetch_holdings'")

    with sq.connect(get_db_path(location)) as connection:
        rows = connection.execute(f"SELECT * FROM {HOLDINGS_DB_NAME} ORDER BY kind, name").fetchall()

    return [(row[0], Holding.init_from_tuple(row[1:])) for row in rows]


def compute_holding_value(holding: Holding) -> float | None:
    """Computes a holding's current market value.

    Args:
        holding (`:class:Holding`): The holding to value.

    Returns:
        float | None: `quantity * last_price`, or `None` if `last_price` hasn't been fetched yet.
    """
    return holding.quantity * holding.last_price if holding.last_price is not None else None


def refresh_holding_price(location: DbLocation, holding_id: int, holding: Holding) -> Holding | None:
    """Fetches a holding's latest price and persists it if found.

    Args:
        location (`:class:DbLocation`): The year/profile of the holding in the database.
        holding_id (int): The id of the row to update.
        holding (`:class:Holding`): The holding whose `ticker` to look up.

    Returns:
        Holding | None: The updated holding if a price was found, `None` if the fetch failed -
            in which case the stored price is left untouched, so the UI keeps showing the last
            known value.
    """
    logger.info("Called 'refresh_holding_price'")

    price = fetch_price(holding.ticker)
    if price is None:
        return None

    updated = replace(holding, last_price=price, last_price_updated=date.today().isoformat())
    edit_item(location, holding_id, holding, updated)
    logger.debug(f"Refreshed price for holding {holding_id} ('{holding.ticker}'): {price}")

    return updated


def fetch_region_allocations(location: DbLocation) -> dict[int, dict[str, float]]:
    """Fetches every holding's region breakdown at once.

    Args:
        location (`:class:DbLocation`): The year/profile of the holdings in the database.

    Returns:
        dict[int, dict[str, float]]: For each holding id, a `{region: percentage}` mapping of its
            entered breakdown. Holdings with no entered breakdown are simply absent.
    """
    logger.info("Called 'fetch_region_allocations'")

    with sq.connect(get_db_path(location)) as connection:
        rows = connection.execute(
            f"SELECT holding_id, region, percentage FROM {HOLDING_REGION_ALLOCATIONS_DB_NAME}"
        ).fetchall()

    allocations: dict[int, dict[str, float]] = {}
    for holding_id, region, percentage in rows:
        allocations.setdefault(holding_id, {})[region] = percentage

    return allocations


def save_region_allocations(location: DbLocation, holding_id: int, allocations: dict[str, float]) -> None:
    """Replaces a holding's entire region breakdown.

    Args:
        location (`:class:DbLocation`): The year/profile of the holding in the database.
        holding_id (int): The id of the holding whose breakdown to replace.
        allocations (dict[str, float]): The new `{region: percentage}` breakdown.
    """
    logger.info("Called 'save_region_allocations'")

    with sq.connect(get_db_path(location)) as connection:
        connection.execute(f"DELETE FROM {HOLDING_REGION_ALLOCATIONS_DB_NAME} WHERE holding_id = ?", (holding_id,))

    for region, percentage in allocations.items():
        add_item(location, HoldingRegionAllocation(holding_id=holding_id, region=region, percentage=percentage))

    logger.debug(f"Saved region allocations for holding {holding_id}:\n{allocations}")


def delete_holding(location: DbLocation, holding_id: int) -> bool:
    """Deletes a holding and its region allocations.

    Args:
        location (`:class:DbLocation`): The year/profile of the holding in the database.
        holding_id (int): The id of the holding to delete.

    Returns:
        bool: `True` if the holding was deleted, `False` otherwise.
    """
    logger.info("Called 'delete_holding'")

    with sq.connect(get_db_path(location)) as connection:
        connection.execute(f"DELETE FROM {HOLDING_REGION_ALLOCATIONS_DB_NAME} WHERE holding_id = ?", (holding_id,))

    return remove_item(location, WhichDb.HOLDINGS, holding_id)
