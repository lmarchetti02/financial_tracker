"""Implementation of the main operations on the holdings database."""

import sqlite3 as sq
from dataclasses import replace
from datetime import date
from logging import getLogger

from _helpers.constants import HOLDINGS_DB_NAME
from _helpers.market_data import fetch_price

from ..data_structures import Holding
from .generic import DbLocation, edit_item, get_db_path

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
