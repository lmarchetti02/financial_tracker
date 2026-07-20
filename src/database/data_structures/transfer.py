"""Implementation of the `:class:Transfer` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row
from typing import Self

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from helpers.constants import TRANSFERS_DB_NAME

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
    """

    db_name = TRANSFERS_DB_NAME

    month: int = Field(gt=0, lt=13)
    kind: Kind
    description: str
    source: str | None = None
    destination: str | None = None
    amount: float = Field(gt=0.0)

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
            DataColumn2(
                label=ft.Row(controls=[ft.Text("M")], tight=True, spacing=0, alignment=ft.MainAxisAlignment.CENTER),
                numeric=True,
                fixed_width=80,
            ),
            DataColumn2(label=ft.Text("Kind"), fixed_width=150),
            DataColumn2(label=ft.Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Source"), fixed_width=200),
            DataColumn2(label=ft.Text("Destination"), fixed_width=200),
            DataColumn2(label=ft.Text("Amount (€)"), numeric=True, fixed_width=150),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        source = str(row["source"]).lower().capitalize().replace("_", " ") if row["source"] is not None else "—"
        destination = (
            str(row["destination"]).lower().capitalize().replace("_", " ") if row["destination"] is not None else "—"
        )

        return [
            ft.DataCell(ft.Container(ft.Text(str(row["month"])), alignment=ft.Alignment.CENTER)),
            ft.DataCell(ft.Text(str(row["kind"]).lower().capitalize().replace("_", " "))),
            ft.DataCell(ft.Text(f"{row['description']}")),
            ft.DataCell(ft.Text(source)),
            ft.DataCell(ft.Text(destination)),
            ft.DataCell(ft.Text(f"{row['amount']:.2f}")),
        ]
