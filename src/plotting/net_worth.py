"""Plots summaries of the net worth."""

from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np

from _helpers.constants import MONTHS
from database import (fetch_net_worth_components,
                      fetch_previous_year_end_net_worth_components)

logger = getLogger("financial_tracker")


def show_net_worth_summary(page: ft.Page) -> None:
    """Generates a line plot of net worth by month, with the previous year-end as a dotted reference line."""
    logger.info("Called 'show_net_worth_summary'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retrieve the current year.")
    year = int(year)

    # get data
    liquid_assets, pension, credits, debts = fetch_net_worth_components(year)
    net_worth = liquid_assets + pension + credits - debts

    prev_liquid_assets, prev_pension, prev_credits, prev_debts = fetch_previous_year_end_net_worth_components(year)
    previous_year_end = prev_liquid_assets + prev_pension + prev_credits - prev_debts

    if not net_worth.any() and previous_year_end == 0.0:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("No balances logged yet"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)

    # plot
    fig = plt.figure()

    plt.axhline(previous_year_end, linestyle="--", color="firebrick", linewidth=1.5, label=f"{year - 1} year-end")
    plt.plot(months, net_worth, marker="o", color="#1565C0", linewidth=2, markersize=6, label=str(year))

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

    plt.title(f"Net Worth Summary {year}")
    plt.ylabel("Net Worth (€)", fontsize=12)
    plt.legend()

    fig.tight_layout()

    # show popup
    if page.width is None or page.height is None:
        raise RuntimeError("Cannot retrieve the page size.")

    chart = fch.MatplotlibChartWithToolbar(figure=fig, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    popup = ft.AlertDialog(
        content=ft.Container(chart, width=page.width * 0.9, height=page.height * 0.8),
        actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
    )

    page.show_dialog(popup)
    page.update()
