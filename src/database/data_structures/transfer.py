"""Implementation of the `:class:Transfer` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row
from typing import Self

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from _helpers.constants import TRANSFERS_DB_NAME
from _helpers.formatting import enum_label

from .base import DataContainer

logger = getLogger("financial_tracker")


class Kind(Enum):
    """Enum with all the possible kinds of transfers."""

    LOAN = auto()
    CREDIT = auto()
    DEBT = auto()
    INVESTMENT = auto()


@dataclass(frozen=True, kw_only=True)
class Transfer(DataContainer):
    """Transfer blueprint.

    Attributes:
        month (int): The month of the transfer (between 1 and 12).
        kind (Kind): The kind of transfer. See `:enum:Kind`.
        description (str): The description of the transfer.
        source (str | None): Where/from whom the transfer comes from. Defaults to `None`.
        destination (str | None): To where/whom the transfer goes to. Defaults to `None`.
        amount (float): The cost of the transfer (greater than zero).
        day (int): The day of the transfer (between 1 and 31). Defaults to 1.
        fee (float | None): The trading fee associated with the transfer, if any. Logged as an
            `:class:Expense` with category `:enum:Categories.TRADING_FEE`. Defaults to `None`.
        fee_expense_id (int | None): The id of the `:class:Expense` row generated for `fee`, used
            to keep it in sync when the transfer is edited or deleted. Defaults to `None`.
        profit (float | None): The profit realized on the transfer, if any. Logged as an
            `:class:Income` with source `:enum:Sources.INVESTMENTS`. Defaults to `None`.
        profit_income_id (int | None): The id of the `:class:Income` row generated for `profit`,
            used to keep it in sync when the transfer is edited or deleted. Defaults to `None`.
    """

    db_name = TRANSFERS_DB_NAME

    month: int = Field(gt=0, lt=13)
    kind: Kind
    description: str
    source: str | None = None
    destination: str | None = None
    amount: float = Field(gt=0.0)
    day: int = Field(default=1, gt=0, lt=32)
    fee: float | None = Field(default=None, gt=0.0)
    fee_expense_id: int | None = None
    profit: float | None = Field(default=None, gt=0.0)
    profit_income_id: int | None = None

    @model_validator(mode="after")
    def valid_source_or_destination(self) -> Self:
        """Validates that at least one of `source`/`destination` is set."""
        if self.source is None and self.destination is None:
            raise ValueError("A transfer must have a source or a destination.")

        return self

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'Transfer.get_table_columns'")

        return [
            Transfer.month_column(),
            DataColumn2(label=ft.Container(ft.Text("D"), alignment=ft.Alignment.CENTER), fixed_width=70),
            DataColumn2(label=ft.Row(controls=[ft.Text("Kind")], tight=True, spacing=5), fixed_width=130),
            DataColumn2(label=ft.Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Source"), fixed_width=150),
            DataColumn2(label=ft.Text("Destination"), fixed_width=150),
            DataColumn2(label=ft.Text("Amount (€)"), numeric=True, fixed_width=130),
            DataColumn2(label=ft.Text("Fee (€)"), numeric=True, fixed_width=100),
            DataColumn2(label=ft.Text("Profit (€)"), numeric=True, fixed_width=100),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        fee = f"{row['fee']:.2f}" if row["fee"] is not None else "—"
        profit = f"{row['profit']:.2f}" if row["profit"] is not None else "—"
        source = row["source"] if row["source"] is not None else "—"
        destination = row["destination"] if row["destination"] is not None else "—"
        return [
            Transfer.month_cell(row),
            ft.DataCell(ft.Container(ft.Text(str(row["day"])), alignment=ft.Alignment.CENTER)),
            ft.DataCell(ft.Text(enum_label(Kind[row["kind"]]))),
            ft.DataCell(ft.Text(f"{row['description']}")),
            ft.DataCell(ft.Text(source)),
            ft.DataCell(ft.Text(destination)),
            ft.DataCell(ft.Text(f"{row['amount']:.2f}")),
            ft.DataCell(ft.Text(fee)),
            ft.DataCell(ft.Text(profit)),
        ]
