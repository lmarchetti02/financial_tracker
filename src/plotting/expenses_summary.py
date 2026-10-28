"""Plots summaries of the expenses."""

from logging import getLogger

import flet as ft

from database import fetch_categories, fetch_category, fetch_expense_totals

from ._common import show_lookup_pie, show_lookup_summary, show_monthly_trend

logger = getLogger("financial_tracker")


def show_expenses_summary(page: ft.Page, category: str | None = None) -> None:
    """Generates the plot showing a summary of the expenses, optionally filtered to one category."""
    logger.info("Called 'show_expenses_summary'")

    show_lookup_summary(page, "Expenses", category, fetch_categories, fetch_category)


def show_expenses_trend(page: ft.Page) -> None:
    """Generates a line plot of total expenses by month, with the yearly average as a dotted reference line."""
    logger.info("Called 'show_expenses_trend'")

    show_monthly_trend(
        page, "Expenses", fetch_expense_totals, color="#960000", empty_text="Empty monthly expenses", lower_is_better=True
    )


def show_expenses_pie(page: ft.Page, month: int | None = None) -> None:
    """Generates the plot showing a pie chart summary of the expenses."""
    logger.info("Called 'show_expenses_pie'")

    show_lookup_pie(page, "Expenses", month, fetch_categories, fetch_category, empty_text="Empty monthly expenses")
