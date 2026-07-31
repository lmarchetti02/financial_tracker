"""Implementation of the `:class:Holding` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field
from pydantic.dataclasses import dataclass

from _helpers.constants import (HOLDING_KIND_TARGETS_DB_NAME,
                                HOLDING_REGION_ALLOCATIONS_DB_NAME,
                                HOLDINGS_DB_NAME)
from _helpers.formatting import enum_label, format_amount

from .base import DataContainer

logger = getLogger("financial_tracker")


class HoldingKind(Enum):
    """Enum with all the possible asset-class exposures of a portfolio holding."""

    STOCKS = auto()
    BONDS = auto()
    COMMODITIES = auto()
    CRYPTO = auto()


class ReplicationMethod(Enum):
    """Enum with the possible ways an ETF replicates its underlying index."""

    FULL = auto()
    SAMPLED = auto()
    SYNTHETIC = auto()


class DistributionPolicy(Enum):
    """Enum with the possible ways a fund handles the earnings it generates."""

    ACCUMULATING = auto()
    DISTRIBUTING = auto()


HOLDING_KIND_COLORS = {
    HoldingKind.STOCKS: "#0D47A1",
    HoldingKind.BONDS: "#6A1B9A",
    HoldingKind.COMMODITIES: "#FF8F00",
    HoldingKind.CRYPTO: "#FDD835",
}

HOLDING_KIND_ICONS = {
    HoldingKind.STOCKS: ft.Icons.TRENDING_UP,
    HoldingKind.BONDS: ft.Icons.ACCOUNT_BALANCE,
    HoldingKind.COMMODITIES: ft.Icons.DIAMOND,
    HoldingKind.CRYPTO: ft.Icons.CURRENCY_BITCOIN,
}


@dataclass(frozen=True, kw_only=True)
class Holding(DataContainer):
    """Holding blueprint: a single portfolio position (ETF/ETC/bond/stock/...).

    Attributes:
        name (str): Free-text display label for the holding, e.g. "FTSE AllWld UCITS ETF USD A
            (XETR:VWCE)". May include the ticker for readability, independent of `ticker`.
        ticker (str): The yfinance-compatible lookup symbol (e.g. "VWCE.DE"), used to fetch
            `last_price`.
        kind (HoldingKind): The asset-class exposure of the holding. See `:enum:HoldingKind`.
        issuer (str): The fund provider/issuer, e.g. "Vanguard".
        currency (str): The holding's base currency (manual; purely informational, the app
            performs no currency conversion).
        region (str | None): An approximate, free-text geographic label, e.g. "All-world".
            Defaults to `None`. For a real aggregate breakdown see `:class:HoldingRegionAllocation`.
        replication (ReplicationMethod | None): How an ETF replicates its index. Defaults to
            `None`, since it doesn't apply to every holding (e.g. a directly-held bond/stock).
        distribution (DistributionPolicy | None): Whether the fund pays out or reinvests
            earnings. Defaults to `None`, for the same reason as `replication`.
        notes (str | None): Free-text notes. Defaults to `None`.
        ter (float | None): The total expense ratio, as a percentage (manual). Defaults to `None`.
        quantity (float): The number of shares/units currently held. Defaults to 0.0.
        last_price (float | None): The most recently fetched price for `ticker`. Defaults to
            `None` until a price refresh succeeds.
        last_price_updated (str | None): The ISO date `last_price` was fetched on. Defaults to
            `None`.
    """

    db_name = HOLDINGS_DB_NAME

    name: str
    ticker: str
    kind: HoldingKind
    issuer: str
    currency: str
    replication: ReplicationMethod | None = None
    distribution: DistributionPolicy | None = None
    notes: str | None = None
    ter: float | None = Field(default=None, ge=0.0)
    quantity: float = Field(default=0.0, ge=0.0)
    # These 3 must stay declared last: `add_missing_columns` always appends new columns to the
    # physical end of an already-existing table, mirroring the same convention in `Transfer`.
    last_price: float | None = None
    last_price_updated: str | None = None
    region: str | None = None

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'Holding.get_table_columns'")

        return [
            DataColumn2(label=ft.Text("Name"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Ticker"), fixed_width=110),
            DataColumn2(label=ft.Text("Kind"), fixed_width=120),
            DataColumn2(label=ft.Text("Issuer"), fixed_width=130),
            DataColumn2(label=ft.Text("Currency"), fixed_width=100),
            DataColumn2(label=ft.Text("Region"), fixed_width=130),
            DataColumn2(label=ft.Text("Replication"), fixed_width=110),
            DataColumn2(label=ft.Text("Distribution"), fixed_width=120),
            DataColumn2(label=ft.Text("Notes"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("TER (%)"), numeric=True, fixed_width=90),
            DataColumn2(label=ft.Text("Shares"), numeric=True, fixed_width=100),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        region = row["region"] if row["region"] is not None else "—"
        replication = enum_label(ReplicationMethod[row["replication"]]) if row["replication"] is not None else "—"
        distribution = enum_label(DistributionPolicy[row["distribution"]]) if row["distribution"] is not None else "—"
        notes = row["notes"] if row["notes"] is not None else "—"
        ter = f"{format_amount(row['ter'], decimals=2)}%" if row["ter"] is not None else "—"

        return [
            ft.DataCell(ft.Text(row["name"])),
            ft.DataCell(ft.Text(row["ticker"])),
            ft.DataCell(ft.Text(enum_label(HoldingKind[row["kind"]]))),
            ft.DataCell(ft.Text(row["issuer"])),
            ft.DataCell(ft.Text(row["currency"])),
            ft.DataCell(ft.Text(region)),
            ft.DataCell(ft.Text(replication)),
            ft.DataCell(ft.Text(distribution)),
            ft.DataCell(ft.Text(notes)),
            ft.DataCell(ft.Text(ter)),
            ft.DataCell(ft.Text(format_amount(row["quantity"], decimals=4))),
        ]


@dataclass(frozen=True, kw_only=True)
class HoldingRegionAllocation(DataContainer):
    """One region's share of a holding's geographic exposure.

    Attributes:
        holding_id (int): The id of the `:class:Holding` this allocation belongs to.
        region (str): The canonical region name (validated against the `regions` lookup list).
        percentage (float): This region's share of the holding's value, in percent (0, 100].
    """

    db_name = HOLDING_REGION_ALLOCATIONS_DB_NAME

    holding_id: int
    region: str
    percentage: float = Field(gt=0.0, le=100.0)

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'HoldingRegionAllocation.get_table_columns'")

        return [
            DataColumn2(label=ft.Text("Region"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Percentage (%)"), numeric=True, fixed_width=120),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            ft.DataCell(ft.Text(row["region"])),
            ft.DataCell(ft.Text(format_amount(row["percentage"], decimals=2))),
        ]


@dataclass(frozen=True, kw_only=True)
class HoldingKindTarget(DataContainer):
    """One asset-class's target share of the portfolio's total value.

    Attributes:
        kind (HoldingKind): The asset-class exposure this target applies to.
        percentage (float): This kind's target share of total portfolio value, in percent (0, 100].
    """

    db_name = HOLDING_KIND_TARGETS_DB_NAME

    kind: HoldingKind
    percentage: float = Field(gt=0.0, le=100.0)

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'HoldingKindTarget.get_table_columns'")

        return [
            DataColumn2(label=ft.Text("Kind"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Percentage (%)"), numeric=True, fixed_width=120),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            ft.DataCell(ft.Text(enum_label(HoldingKind[row["kind"]]))),
            ft.DataCell(ft.Text(format_amount(row["percentage"], decimals=2))),
        ]
