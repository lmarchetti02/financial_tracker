"""Implementation of the `:class:Expense` class."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row
from typing import Self

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from _helpers.constants import EXPENSES_DB_NAME

from .base import DataContainer

logger = getLogger("financial_tracker")


class Categories(Enum):
    """Enum with all the possible categories of expenses."""

    COUPLE = auto()
    EDUCATION = auto()
    ENTERTAINMENT = auto()
    FOOD_AND_DRINKS = auto()
    SUBSCRIPTIONS = auto()
    PERSONAL_ITEMS = auto()
    PRESENTS = auto()
    TRAVEL = auto()
    TRADING_FEE = auto()
    INTEREST_ON_DEBT = auto()
    OTHER = auto()


@dataclass(frozen=True, kw_only=True)
class Expense(DataContainer):
    """Expense blueprint.

    Attributes:
        month (int): The month of the expense (between 1 and 12).
        day_start (int): The day of the expense (between 1 and 31). If the expense refers
            to a period of time longer than 1 day, this is the initial day.
        day_start (int): The final day of the expense if said expense refers to a period
            of time longer than 1 day (between `day_start` and 31).
            Otherwise, defaults to `None`.
        description (str): The description of the expense.
        category (Categories): The category of the expense. See `:enum:Categories`.
        cost (float): The cost of the expense (greater than zero).
    """

    db_name = EXPENSES_DB_NAME

    month: int = Field(gt=0, lt=13)
    day_start: int = Field(gt=0, lt=32)
    day_end: int | None = Field(default=None, gt=0, lt=32)
    description: str
    category: Categories
    cost: float = Field(gt=0.0)

    @model_validator(mode="after")
    def valid_day_end(self) -> Self:
        """Validates the `day_end` attribute."""
        if self.day_end is not None and self.day_end < self.day_start:
            raise ValueError("End date cannot be before start date.")

        return self

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'get_table_columns'")

        return [
            DataColumn2(
                label=ft.Row(controls=[ft.Text("M")], tight=True, spacing=0, alignment=ft.MainAxisAlignment.CENTER),
                numeric=True,
                fixed_width=80,
            ),
            DataColumn2(label=ft.Container(ft.Text("D"), alignment=ft.Alignment.CENTER), fixed_width=100),
            DataColumn2(label=ft.Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Category"), fixed_width=200),
            DataColumn2(label=ft.Text("Cost (€)"), numeric=True, fixed_width=100),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        if row["day_end"] is not None:
            days = f"{row['day_start']}-{row['day_end']}"
        else:
            days = str(row["day_start"])
        return [
            ft.DataCell(ft.Container(ft.Text(str(row["month"])), alignment=ft.Alignment.CENTER)),
            ft.DataCell(ft.Container(ft.Text(days), alignment=ft.Alignment.CENTER)),
            ft.DataCell(ft.Text(str(row["description"]))),
            ft.DataCell(ft.Text(str(row["category"]).lower().capitalize().replace("_", " "))),
            ft.DataCell(ft.Text(f"{row['cost']:.2f}")),
        ]
