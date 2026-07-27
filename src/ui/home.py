"""Implementation of the home layout."""

from collections.abc import Callable
from logging import getLogger

import flet as ft
import numpy as np
from flet_datatable2 import DataColumn2

import database as db
from _helpers.constants import MONTHS
from _helpers.formatting import format_amount
from plotting import show_net_worth_summary, show_savings_pie, show_savings_summary

from .common import build_styled_data_table, current_db_location

logger = getLogger("financial_tracker")

_HEADING_COLOR = "#FBC02D"
_NET_WORTH_HEADING_COLOR = "#64B5F6"


def home_view(page: ft.Page) -> ft.Control:
    """Implementation of the home view."""
    logger.info("Called 'home_view'")

    location = current_db_location(page)

    income = db.fetch_income_totals(location)
    expenses = db.fetch_expense_totals(location)
    net_savings = income - expenses

    savings_rate = np.zeros_like(income)
    np.divide(net_savings, income, out=savings_rate, where=income != 0)
    savings_rate *= 100

    logger.debug(f"Income per month:\n{income}")
    logger.debug(f"Expenses per month:\n{expenses}")
    logger.debug(f"Net savings per month:\n{net_savings}")
    logger.debug(f"Savings rate per month:\n{savings_rate}")

    def build_savings_columns() -> list[DataColumn2]:
        """Builds a blank label column followed by one numeric column per month."""
        return [DataColumn2(label=ft.Text(""), fixed_width=170)] + [
            DataColumn2(label=ft.Text(month), numeric=True) for month in MONTHS
        ]

    def build_savings_row(label: str, values: np.ndarray, formatter: Callable[[float], str]) -> ft.DataRow:
        """Builds a `:class:DataRow` with a label cell followed by one formatted cell per month."""
        return ft.DataRow(cells=[ft.DataCell(ft.Text(label))] + [ft.DataCell(ft.Text(formatter(v))) for v in values])

    def build_net_worth_columns() -> list[DataColumn2]:
        """Builds a blank label column, the previous year, then one numeric column per month."""
        return [
            DataColumn2(label=ft.Text(""), fixed_width=170),
            DataColumn2(label=ft.Text(str(location.year - 1)), numeric=True),
        ] + [DataColumn2(label=ft.Text(month), numeric=True) for month in MONTHS]

    def build_net_worth_row(
        label: str,
        previous_year_value: float,
        values: np.ndarray,
        formatter: Callable[[float], str],
        bold: bool = False,
    ) -> ft.DataRow:
        """Builds a `:class:DataRow` with a label, the previous year's value, then one cell per month."""
        weight = ft.FontWeight.BOLD if bold else None
        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(label, weight=weight)),
                ft.DataCell(ft.Text(formatter(previous_year_value), weight=weight)),
            ]
            + [ft.DataCell(ft.Text(formatter(v), weight=weight)) for v in values]
        )

    def format_eur(value: float) -> str:
        """Formats a home-page EUR value, rounded to whole euros."""
        return format_amount(value, decimals=0)

    savings_columns = build_savings_columns()
    savings_rows = [
        build_savings_row("Income (€)", income, format_eur),
        build_savings_row("Expenses (€)", expenses, format_eur),
        build_savings_row("Net Savings (€)", net_savings, format_eur),
        build_savings_row("Savings Rate (%)", savings_rate, lambda v: f"{v:.1f}"),
    ]
    savings_table = build_styled_data_table(savings_columns, savings_rows, _HEADING_COLOR)

    liquid_assets, pension, credits, debts = db.fetch_net_worth_components(location)
    net_worth = liquid_assets + pension + credits - debts

    prev_liquid_assets, prev_pension, prev_credits, prev_debts = db.fetch_previous_year_end_net_worth_components(
        location
    )
    prev_net_worth = prev_liquid_assets + prev_pension + prev_credits - prev_debts

    logger.debug(f"Liquid assets per month:\n{liquid_assets}")
    logger.debug(f"Pension fund per month:\n{pension}")
    logger.debug(f"Credits per month:\n{credits}")
    logger.debug(f"Debts per month:\n{debts}")
    logger.debug(f"Net worth per month:\n{net_worth}")

    net_worth_rows = [
        build_net_worth_row("Liquid Assets (€)", prev_liquid_assets, liquid_assets, format_eur),
        build_net_worth_row("Pension Fund (€)", prev_pension, pension, format_eur),
        build_net_worth_row("Credits (€)", prev_credits, credits, format_eur),
        build_net_worth_row("Debts (€)", prev_debts, debts, format_eur),
        build_net_worth_row("Total (€)", prev_net_worth, net_worth, format_eur, bold=True),
    ]
    net_worth_table = build_styled_data_table(build_net_worth_columns(), net_worth_rows, _NET_WORTH_HEADING_COLOR)

    summary_button = ft.Button(
        "Show Summary",
        icon=ft.Icons.BAR_CHART,
        color="#006400",
        on_click=lambda _: show_savings_summary(page),
    )
    pie_chart_button = ft.Button(
        "Show Pie Chart",
        icon=ft.Icons.BAR_CHART,
        color="#000096",
        on_click=lambda _: show_savings_pie(page),
    )
    net_worth_summary_button = ft.Button(
        "Show Summary",
        icon=ft.Icons.BAR_CHART,
        color="#1565C0",
        on_click=lambda _: show_net_worth_summary(page),
    )

    return ft.Column(
        controls=[
            ft.Text("Home", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=30),
            ft.Text("Savings", size=20, weight=ft.FontWeight.BOLD),
            savings_table,
            ft.Container(height=10),
            ft.Row([summary_button, pie_chart_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=30),
            ft.Text("Net Worth", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            net_worth_table,
            ft.Container(height=10),
            ft.Row([net_worth_summary_button], alignment=ft.MainAxisAlignment.CENTER),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )
