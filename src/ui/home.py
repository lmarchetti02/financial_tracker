"""Implementation of the home layout."""

from logging import getLogger

import flet as ft
import numpy as np
from flet_datatable2 import DataColumn2

import database as db
from _helpers.constants import MONTHS
from plotting import show_savings_pie, show_savings_summary

from .common import build_styled_data_table

logger = getLogger("financial_tracker")

_HEADING_COLOR = "#FBC02D"


def home_view(page: ft.Page) -> ft.Control:
    """Implementation of the home view."""
    logger.info("Called 'home_view'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retrieve the current year.")
    year = int(year)

    income = db.fetch_income_totals(year)
    expenses = db.fetch_expense_totals(year)
    net_savings = income - expenses

    savings_rate = np.zeros_like(income)
    np.divide(net_savings, income, out=savings_rate, where=income != 0)
    savings_rate *= 100

    logger.debug(f"Income per month:\n{income}")
    logger.debug(f"Expenses per month:\n{expenses}")
    logger.debug(f"Net savings per month:\n{net_savings}")
    logger.debug(f"Savings rate per month:\n{savings_rate}")

    def build_row(label: str, values: np.ndarray, fmt: str) -> ft.DataRow:
        """Builds a `:class:DataRow` with a label cell followed by one formatted cell per month."""
        return ft.DataRow(cells=[ft.DataCell(ft.Text(label))] + [ft.DataCell(ft.Text(fmt.format(v))) for v in values])

    columns = [DataColumn2(label=ft.Text(""), fixed_width=150)] + [
        DataColumn2(label=ft.Text(month), numeric=True) for month in MONTHS
    ]
    rows = [
        build_row("Income (€)", income, "{:.2f}"),
        build_row("Expenses (€)", expenses, "{:.2f}"),
        build_row("Net Savings (€)", net_savings, "{:.2f}"),
        build_row("Savings Rate (%)", savings_rate, "{:.1f}"),
    ]
    table = build_styled_data_table(columns, rows, _HEADING_COLOR)

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

    return ft.Column(
        controls=[
            ft.Text("Home", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=30),
            table,
            ft.Container(height=10),
            ft.Row([summary_button, pie_chart_button], alignment=ft.MainAxisAlignment.CENTER),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )
