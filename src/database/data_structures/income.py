"""Implementation of the `:class:Income` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field
from pydantic.dataclasses import dataclass

from helpers.constants import INCOME_DB_NAME

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
            DataColumn2(
                label=ft.Row(controls=[ft.Text("M")], tight=True, spacing=0, alignment=ft.MainAxisAlignment.CENTER),
                numeric=True,
                fixed_width=80,
            ),
            DataColumn2(label=ft.Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Source"), fixed_width=200),
            DataColumn2(label=ft.Text("Amount (€)"), numeric=True, fixed_width=150),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            ft.DataCell(ft.Container(ft.Text(str(row["month"])), alignment=ft.Alignment.CENTER)),
            ft.DataCell(ft.Text(f"{row['description']}")),
            ft.DataCell(ft.Text(str(row["source"]).lower().capitalize().replace("_", " "))),
            ft.DataCell(ft.Text(f"{row['amount']:.2f}")),
        ]
