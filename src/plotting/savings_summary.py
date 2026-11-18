"""Plots summaries of the net savings."""

from logging import getLogger

import flet as ft
import matplotlib.pyplot as plt
import numpy as np

from _helpers.constants import MONTHS
from _helpers.formatting import format_amount
from database import fetch_expense_totals, fetch_income_totals
from ui.colors import CHART_BASELINE_COLOR, HOME_ACCENT, NEGATIVE_COLOR, POSITIVE_COLOR

from ._common import PIE_WEDGE_PROPS, current_db_location, show_chart_popup, show_empty_popup

logger = getLogger("financial_tracker")


def show_savings_summary(page: ft.Page) -> None:
    """Generates the plot showing a summary of the net savings."""
    logger.info("Called 'show_savings_summary'")

    location = current_db_location(page)

    # get data
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    net_savings = fetch_income_totals(location) - fetch_expense_totals(location)

    # plot
    fig = plt.figure()

    plt.axhline(0, color=CHART_BASELINE_COLOR, linewidth=1)
    plt.fill_between(months, net_savings, 0, where=net_savings >= 0, color=POSITIVE_COLOR, alpha=0.3, interpolate=True)
    plt.fill_between(months, net_savings, 0, where=net_savings <= 0, color=NEGATIVE_COLOR, alpha=0.3, interpolate=True)
    plt.plot(months, net_savings, marker="o", color=HOME_ACCENT, linewidth=2, markersize=6)

    plt.grid(axis="y", linestyle="--")
    plt.grid(axis="x", linestyle="--")
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    plt.title(f"Savings Summary {location.year}")
    plt.ylabel("Net Savings (€)")

    fig.tight_layout()

    show_chart_popup(page, fig)


def show_savings_pie(page: ft.Page) -> None:
    """Generates the plot showing how much of the year's income was saved versus spent."""
    logger.info("Called 'show_savings_pie'")

    location = current_db_location(page)

    # get data
    total_income = fetch_income_totals(location).sum()
    total_expenses = fetch_expense_totals(location).sum()
    total_saved = total_income - total_expenses

    values = np.array([total_saved, total_expenses], dtype=np.float32)
    names = np.array(["Saved", "Spent"], dtype=str)

    # remove non-positive slices (e.g. a deficit year has nothing "saved" to show)
    mask = values > 0
    values = values[mask]
    names = names[mask]
    if not values.size > 0:
        show_empty_popup(page, "Empty yearly income")
        return

    # plot
    fig = plt.figure()

    color_map = {"Saved": POSITIVE_COLOR, "Spent": NEGATIVE_COLOR}
    colors = [color_map[name] for name in names]

    plt.title(f"Savings Pie Chart ({location.year})")
    patches, *_ = plt.pie(
        values, labels=names, colors=colors, autopct="%1.1f%%", wedgeprops=PIE_WEDGE_PROPS
    )  # type: ignore

    legend_labels = [f"{name}: € {format_amount(val, decimals=0)}" for name, val in zip(names, values)]
    plt.legend(
        patches,
        legend_labels,
        title="Savings",
        title_fontproperties={"weight": "bold"},
        loc="center left",
        bbox_to_anchor=(1.2, 0, 0.5, 1),
    )

    fig.tight_layout()

    show_chart_popup(page, fig)
