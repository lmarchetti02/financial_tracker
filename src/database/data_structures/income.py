"""Implementation of the `:class:Income` class."""

from logging import getLogger
from sqlite3 import Row

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field
from pydantic.dataclasses import dataclass

from _helpers.constants import INCOME_DB_NAME
from _helpers.formatting import format_amount

from .base import DataContainer

logger = getLogger("financial_tracker")


@dataclass(frozen=True, kw_only=True)
class Income(DataContainer):
    """Income blueprint.

    Attributes:
        month (int): The month of the expense (between 1 and 12).
        description (str): The description of the income.
        source (str): The source of income, one of the entries managed from the settings page
            (see `database.db_operations.config`).
        amount (float): The cost of the expense (greater than zero).
        amount_expression (str | None): The raw text (a number or an arithmetic expression) the
            user typed into the amount field, redisplayed when editing the income. `None` for
            rows created before this field existed. Defaults to `None`.
    """

    db_name = INCOME_DB_NAME

    month: int = Field(gt=0, lt=13)
    source: str
    description: str
    amount: float = Field(gt=0.0)
    amount_expression: str | None = None

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
            ft.DataCell(ft.Text(str(row["source"]))),
            ft.DataCell(ft.Text(format_amount(row["amount"]))),
        ]
