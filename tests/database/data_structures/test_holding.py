"""Unit tests for `database.data_structures.holding`."""

import pytest

from database.data_structures.holding import (
    DistributionPolicy,
    Holding,
    HoldingKind,
    HoldingKindTarget,
    HoldingRegionAllocation,
    ReplicationMethod,
)


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


class TestHolding:
    """Tests for `Holding`."""

    def test_construction_succeeds_with_required_fields(self) -> None:
        """Name, ticker, kind, issuer, and currency are enough to build a holding."""
        holding = make_holding()

        assert holding.name == "FTSE AllWld UCITS ETF USD A (XETR:VWCE)"
        assert holding.ticker == "VWCE.DE"
        assert holding.kind == HoldingKind.STOCKS
        assert holding.issuer == "Vanguard"
        assert holding.currency == "USD"

    def test_optional_fields_default_to_none(self) -> None:
        """Region, replication, distribution, notes, and TER are optional."""
        holding = make_holding()

        assert holding.region is None
        assert holding.replication is None
        assert holding.distribution is None
        assert holding.notes is None
        assert holding.ter is None

    def test_quantity_defaults_to_zero(self) -> None:
        """A newly-defined holding starts with no shares/units."""
        assert make_holding().quantity == 0.0

    def test_construction_succeeds_with_replication_and_distribution_set(self) -> None:
        """Replication and distribution can be set to any of their enum members."""
        holding = make_holding(replication=ReplicationMethod.SAMPLED, distribution=DistributionPolicy.ACCUMULATING)

        assert holding.replication == ReplicationMethod.SAMPLED
        assert holding.distribution == DistributionPolicy.ACCUMULATING

    def test_construction_fails_for_negative_quantity(self) -> None:
        """A negative number of shares/units is rejected."""
        with pytest.raises(ValueError):
            make_holding(quantity=-1.0)

    def test_construction_fails_for_negative_ter(self) -> None:
        """A negative TER is rejected."""
        with pytest.raises(ValueError):
            make_holding(ter=-0.1)


class TestHoldingGetTableColumns:
    """Tests for `Holding.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """One column each for name, ticker, kind, issuer, currency, region, replication, distribution, notes, TER, shares."""
        assert len(Holding.get_table_columns()) == 11


class TestHoldingGetTableRow:
    """Tests for `Holding.get_table_row`."""

    def test_formats_populated_fields(self) -> None:
        """Every field is rendered, with the kind/replication/distribution as human-readable labels."""
        row = {
            "name": "FTSE AllWld UCITS ETF USD A (XETR:VWCE)",
            "ticker": "VWCE.DE",
            "kind": "STOCKS",
            "issuer": "Vanguard",
            "currency": "USD",
            "region": "All-world",
            "replication": "SAMPLED",
            "distribution": "ACCUMULATING",
            "notes": "Large/medium-sized companies",
            "ter": 0.21,
            "quantity": 5.0,
        }

        cells = Holding.get_table_row(row)

        assert cells[0].content.value == "FTSE AllWld UCITS ETF USD A (XETR:VWCE)"
        assert cells[1].content.value == "VWCE.DE"
        assert cells[2].content.value == "Stocks"
        assert cells[3].content.value == "Vanguard"
        assert cells[4].content.value == "USD"
        assert cells[5].content.value == "All-world"
        assert cells[6].content.value == "Sampled"
        assert cells[7].content.value == "Accumulating"
        assert cells[8].content.value == "Large/medium-sized companies"
        assert cells[9].content.value == "0,21%"
        assert cells[10].content.value == "5,0000"

    def test_formats_unset_optional_fields_as_a_placeholder(self) -> None:
        """Region, replication, distribution, notes, and TER render as "—" when unset."""
        row = {
            "name": "FTSE AllWld UCITS ETF USD A (XETR:VWCE)",
            "ticker": "VWCE.DE",
            "kind": "STOCKS",
            "issuer": "Vanguard",
            "currency": "USD",
            "region": None,
            "replication": None,
            "distribution": None,
            "notes": None,
            "ter": None,
            "quantity": 0.0,
        }

        cells = Holding.get_table_row(row)

        assert cells[5].content.value == "—"
        assert cells[6].content.value == "—"
        assert cells[7].content.value == "—"
        assert cells[8].content.value == "—"
        assert cells[9].content.value == "—"


class TestHoldingRegionAllocation:
    """Tests for `HoldingRegionAllocation`."""

    def test_construction_succeeds_with_valid_percentage(self) -> None:
        """A holding id, region, and percentage between 0 (exclusive) and 100 (inclusive) are enough."""
        allocation = HoldingRegionAllocation(holding_id=1, region="North America", percentage=60.0)

        assert allocation.holding_id == 1
        assert allocation.region == "North America"
        assert allocation.percentage == 60.0

    def test_construction_fails_for_zero_percentage(self) -> None:
        """A zero percentage is rejected — an allocation with nothing in it shouldn't be stored."""
        with pytest.raises(ValueError):
            HoldingRegionAllocation(holding_id=1, region="North America", percentage=0.0)

    def test_construction_fails_for_percentage_above_100(self) -> None:
        """A percentage above 100 is rejected."""
        with pytest.raises(ValueError):
            HoldingRegionAllocation(holding_id=1, region="North America", percentage=100.1)


class TestHoldingKindTarget:
    """Tests for `HoldingKindTarget`."""

    def test_construction_succeeds_with_valid_percentage(self) -> None:
        """A kind and a percentage between 0 (exclusive) and 100 (inclusive) are enough."""
        target = HoldingKindTarget(kind=HoldingKind.STOCKS, percentage=60.0)

        assert target.kind == HoldingKind.STOCKS
        assert target.percentage == 60.0

    def test_construction_fails_for_zero_percentage(self) -> None:
        """A zero percentage is rejected — a target with nothing in it shouldn't be stored."""
        with pytest.raises(ValueError):
            HoldingKindTarget(kind=HoldingKind.STOCKS, percentage=0.0)

    def test_construction_fails_for_percentage_above_100(self) -> None:
        """A percentage above 100 is rejected."""
        with pytest.raises(ValueError):
            HoldingKindTarget(kind=HoldingKind.STOCKS, percentage=100.1)


class TestHoldingKindTargetGetTableColumns:
    """Tests for `HoldingKindTarget.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """One column each for kind and percentage."""
        assert len(HoldingKindTarget.get_table_columns()) == 2


class TestHoldingKindTargetGetTableRow:
    """Tests for `HoldingKindTarget.get_table_row`."""

    def test_formats_the_kind_as_a_human_readable_label(self) -> None:
        """The stored enum name is rendered via `enum_label`, not the raw name."""
        row = {"kind": "STOCKS", "percentage": 60.0}

        cells = HoldingKindTarget.get_table_row(row)

        assert cells[0].content.value == "Stocks"
        assert cells[1].content.value == "60,00"
