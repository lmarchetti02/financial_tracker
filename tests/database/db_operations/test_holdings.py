"""Unit tests for `database.db_operations.holdings`."""

from unittest.mock import patch

from database.data_structures.holding import Holding, HoldingKind
from database.db_operations.generic import DbLocation, WhichDb, add_item, fetch_by_id, initialize_db
from database.db_operations.holdings import fetch_holdings, refresh_holding_price

YEAR = 2024
LOCATION = DbLocation(YEAR)


def make_holding(**overrides: object) -> Holding:
    """Builds a `:class:Holding` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "name": "FTSE AllWld UCITS ETF USD A (XETR:VWCE)",
        "ticker": "VWCE.DE",
        "kind": HoldingKind.STOCKS,
        "issuer": "Vanguard",
        "currency": "USD",
    }
    defaults.update(overrides)
    return Holding(**defaults)


class TestFetchHoldings:
    """Tests for `fetch_holdings`."""

    def test_orders_by_name_within_the_same_kind(self) -> None:
        """Holdings of the same kind are ordered alphabetically by name."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        add_item(LOCATION, make_holding(name="Zeta Fund"))
        add_item(LOCATION, make_holding(name="Alpha Fund"))

        names = [holding.name for _, holding in fetch_holdings(LOCATION)]

        assert names == ["Alpha Fund", "Zeta Fund"]

    def test_orders_by_kind_before_name(self) -> None:
        """Holdings are grouped by kind first, even when that reorders their names."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        add_item(LOCATION, make_holding(name="Zeta Fund", kind=HoldingKind.BONDS))
        add_item(LOCATION, make_holding(name="Alpha Fund", kind=HoldingKind.STOCKS))

        names = [holding.name for _, holding in fetch_holdings(LOCATION)]

        assert names == ["Zeta Fund", "Alpha Fund"]


class TestRefreshHoldingPrice:
    """Tests for `refresh_holding_price`."""

    def test_persists_the_fetched_price_on_success(self) -> None:
        """A successful fetch updates and persists `last_price`/`last_price_updated`."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        holding_id = add_item(LOCATION, make_holding())
        holding = fetch_by_id(LOCATION, WhichDb.HOLDINGS, holding_id)

        with patch("database.db_operations.holdings.fetch_price", return_value=163.74):
            updated = refresh_holding_price(LOCATION, holding_id, holding)

        assert updated is not None
        assert updated.last_price == 163.74
        assert updated.last_price_updated is not None

        persisted = fetch_by_id(LOCATION, WhichDb.HOLDINGS, holding_id)
        assert persisted.last_price == 163.74

    def test_returns_none_and_leaves_the_stored_price_untouched_on_failure(self) -> None:
        """A failed fetch returns `None` without touching the previously stored price."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        holding_id = add_item(LOCATION, make_holding())

        with patch("database.db_operations.holdings.fetch_price", return_value=163.74):
            refresh_holding_price(LOCATION, holding_id, fetch_by_id(LOCATION, WhichDb.HOLDINGS, holding_id))

        holding = fetch_by_id(LOCATION, WhichDb.HOLDINGS, holding_id)

        with patch("database.db_operations.holdings.fetch_price", return_value=None):
            result = refresh_holding_price(LOCATION, holding_id, holding)

        assert result is None
        assert fetch_by_id(LOCATION, WhichDb.HOLDINGS, holding_id).last_price == 163.74
