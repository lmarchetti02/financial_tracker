"""Unit tests for `database.db_operations.holdings`."""

from unittest.mock import patch

import pytest

from database.data_structures.holding import Holding, HoldingKind
from database.db_operations.generic import DbLocation, WhichDb, add_item, fetch_by_id, initialize_db
from database.db_operations.holdings import (
    compute_holding_value,
    delete_holding,
    fetch_holdings,
    fetch_region_allocations,
    refresh_holding_price,
    save_region_allocations,
)

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


class TestComputeHoldingValue:
    """Tests for `compute_holding_value`."""

    def test_multiplies_quantity_by_last_price(self) -> None:
        """A priced holding's value is `quantity * last_price`."""
        holding = make_holding(quantity=3.0, last_price=163.74)

        assert compute_holding_value(holding) == pytest.approx(3.0 * 163.74)

    def test_returns_none_when_unpriced(self) -> None:
        """A holding with no fetched price yet has an unknown value."""
        holding = make_holding(quantity=3.0, last_price=None)

        assert compute_holding_value(holding) is None


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


class TestFetchRegionAllocations:
    """Tests for `fetch_region_allocations`."""

    def test_returns_empty_dict_when_nothing_saved_yet(self) -> None:
        """A holding with no entered breakdown is simply absent from the result."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        add_item(LOCATION, make_holding())

        assert fetch_region_allocations(LOCATION) == {}

    def test_groups_allocations_by_holding(self) -> None:
        """Every holding's breakdown is returned, keyed by its id."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        holding_id = add_item(LOCATION, make_holding())

        save_region_allocations(LOCATION, holding_id, {"North America": 60.0, "Europe": 25.0})

        assert fetch_region_allocations(LOCATION) == {holding_id: {"North America": 60.0, "Europe": 25.0}}


class TestSaveRegionAllocations:
    """Tests for `save_region_allocations`."""

    def test_persists_a_new_breakdown(self) -> None:
        """Saving a breakdown for the first time persists every entry."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        holding_id = add_item(LOCATION, make_holding())

        save_region_allocations(LOCATION, holding_id, {"North America": 60.0})

        assert fetch_region_allocations(LOCATION) == {holding_id: {"North America": 60.0}}

    def test_replaces_the_entire_previous_breakdown(self) -> None:
        """Saving again drops every previously entered region, not just overlapping ones."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        holding_id = add_item(LOCATION, make_holding())

        save_region_allocations(LOCATION, holding_id, {"North America": 60.0, "Europe": 25.0})
        save_region_allocations(LOCATION, holding_id, {"Japan": 100.0})

        assert fetch_region_allocations(LOCATION) == {holding_id: {"Japan": 100.0}}

    def test_does_not_touch_other_holdings_breakdowns(self) -> None:
        """Replacing one holding's breakdown leaves every other holding's breakdown untouched."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        first_id = add_item(LOCATION, make_holding(name="Fund A"))
        second_id = add_item(LOCATION, make_holding(name="Fund B"))

        save_region_allocations(LOCATION, first_id, {"North America": 100.0})
        save_region_allocations(LOCATION, second_id, {"Europe": 100.0})
        save_region_allocations(LOCATION, first_id, {"Japan": 100.0})

        assert fetch_region_allocations(LOCATION) == {
            first_id: {"Japan": 100.0},
            second_id: {"Europe": 100.0},
        }


class TestDeleteHolding:
    """Tests for `delete_holding`."""

    def test_deletes_the_holding(self) -> None:
        """The holding itself is removed."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        holding_id = add_item(LOCATION, make_holding())

        assert delete_holding(LOCATION, holding_id) is True
        assert fetch_holdings(LOCATION) == []

    def test_cascades_to_its_region_allocations(self) -> None:
        """Deleting a holding also removes its region breakdown, leaving no orphaned rows."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)
        holding_id = add_item(LOCATION, make_holding())
        save_region_allocations(LOCATION, holding_id, {"North America": 100.0})

        delete_holding(LOCATION, holding_id)

        assert fetch_region_allocations(LOCATION) == {}

    def test_returns_false_for_a_nonexistent_holding(self) -> None:
        """Deleting an id that doesn't exist reports failure."""
        initialize_db(LOCATION, WhichDb.HOLDINGS)
        initialize_db(LOCATION, WhichDb.HOLDING_REGION_ALLOCATIONS)

        assert delete_holding(LOCATION, 999) is False
