"""Implementation of the `:class:Income` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field
from pydantic.dataclasses import dataclass

from _helpers.constants import INCOME_DB_NAME
from _helpers.formatting import enum_label, format_amount

from .base import DataContainer

logger = getLogger("financial_tracker")


class Sources(Enum):
    """Enum with all the possible sources of income."""

    SALARY = auto()
    PRESENTS = auto()
    INVESTMENTS = auto()
    OTHER = auto()


@dataclass(frozen=True, kw_only=True)
class Income(DataContainer):
    """Income blueprint.

    Attributes:
        month (int): The month of the expense (between 1 and 12).
        description (str): The description of the income.
        source (Categories): The source of income. See `:enum:Source`.
        amount (float): The cost of the expense (greater than zero).
    """

    db_name = INCOME_DB_NAME

    month: int = Field(gt=0, lt=13)
    source: Sources
    description: str
    amount: float = Field(gt=0.0)

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'Income.get_table_columns'")

        return [
            Income.month_column(),
            DataColumn2(label=ft.Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=ft.Row(controls=[ft.Text("Source")], tight=True, spacing=5), fixed_width=200),
            DataColumn2(label=ft.Text("Amount (€)"), numeric=True, fixed_width=150),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            Income.month_cell(row),
            ft.DataCell(ft.Text(f"{row['description']}")),
            ft.DataCell(ft.Text(enum_label(Sources[row["source"]]))),
            ft.DataCell(ft.Text(format_amount(row["amount"]))),
        ]
