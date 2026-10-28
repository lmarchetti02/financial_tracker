"""Plots summaries of the net worth."""

from logging import getLogger

import flet as ft
import matplotlib.pyplot as plt
import numpy as np

from _helpers.constants import MONTHS
from database import fetch_net_worth_components, fetch_previous_year_end_net_worth_components

from ._common import current_db_location, show_chart_popup, show_empty_popup

logger = getLogger("financial_tracker")


def show_net_worth_summary(page: ft.Page) -> None:
    """Generates a line plot of net worth by month, with the previous year-end as a dotted reference line."""
    logger.info("Called 'show_net_worth_summary'")

    location = current_db_location(page)

    # get data
    liquid_assets, pension, credits, debts = fetch_net_worth_components(location)
    net_worth = liquid_assets + pension + credits - debts

    prev_liquid_assets, prev_pension, prev_credits, prev_debts = fetch_previous_year_end_net_worth_components(location)
    previous_year_end = prev_liquid_assets + prev_pension + prev_credits - prev_debts

    if not net_worth.any() and previous_year_end == 0.0:
        show_empty_popup(page, "No balances logged yet")
        return

    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)

    # plot
    fig = plt.figure()

    plt.axhline(
        previous_year_end, linestyle="--", color="firebrick", linewidth=1.5, label=f"{location.year - 1} year-end"
    )
    plt.plot(months, net_worth, color="#1565C0", linewidth=1.2, alpha=0.4, label=str(location.year), zorder=1)
    plt.plot(months, net_worth, marker="o", linestyle="none", color="#1565C0", markersize=6, zorder=2)

    if previous_year_end != 0:
        percent_change = (net_worth - previous_year_end) / previous_year_end * 100
        for month, value, pct in zip(months, net_worth, percent_change):
            plt.annotate(
                f"{pct:+.1f}%",
                (month, value),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                color="darkgreen" if pct >= 0 else "firebrick",
            )

    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    plt.title(f"Net Worth Summary {location.year}")
    plt.ylabel("Net Worth (€)", fontsize=12)
    plt.legend()

    fig.tight_layout()

    show_chart_popup(page, fig)
