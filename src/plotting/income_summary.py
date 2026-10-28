"""Plots summaries of the incomes."""

from logging import getLogger

import flet as ft

from database import fetch_income_totals, fetch_source_totals, fetch_sources

from ._common import show_lookup_pie, show_lookup_summary, show_monthly_trend

logger = getLogger("financial_tracker")


def show_income_summary(page: ft.Page, source: str | None = None) -> None:
    """Generates the plot showing a summary of the incomes, optionally filtered to one source."""
    logger.info("Called 'show_income_summary'")

    show_lookup_summary(page, "Income", source, fetch_sources, fetch_source_totals)


def show_income_trend(page: ft.Page) -> None:
    """Generates a line plot of total income by month, with the yearly average as a dotted reference line."""
    logger.info("Called 'show_income_trend'")

    show_monthly_trend(
        page, "Income", fetch_income_totals, color="#006400", empty_text="Empty monthly income", lower_is_better=False
    )


def show_income_pie(page: ft.Page, month: int | None = None) -> None:
    """Generates the plot showing a pie chart summary of the incomes."""
    logger.info("Called 'show_income_pie'")

    show_lookup_pie(page, "Income", month, fetch_sources, fetch_source_totals, empty_text="Empty monthly income")
