"""Plots summaries of the expenses."""

from itertools import cycle
from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TABLEAU_COLORS

from _helpers.constants import MONTHS
from _helpers.formatting import format_amount
from database import fetch_categories, fetch_category

logger = getLogger("financial_tracker")


def show_expenses_summary(page: ft.Page) -> None:
    """Generates the plot showing a summary of the expenses."""
    logger.info("Called 'show_expenses_summary'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    if (profile := page.session.store.get("selected_profile")) is None:
        raise RuntimeError("Cannot retrieve the current profile.")

    # get data
    categories = fetch_categories()
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = np.zeros((len(months), len(categories)), dtype=np.float32)
    for i, category in enumerate(categories):
        totals[:, i] = fetch_category(year, category, profile)

    # plot
    fig = plt.figure()

    linestyles = cycle(["-", "--", "-.", ":"])
    markers = cycle(["o", "s", "^", "D", "v", "p", "*"])
    colors = cycle(TABLEAU_COLORS)

    for i in range(len(categories)):
        plt.plot(
            months,
            totals[:, i],
            label=categories[i],
            linestyle=next(linestyles),
            marker=next(markers),
            color=next(colors),
            linewidth=2,
            markersize=6,
            alpha=0.8,
        )

    total_per_month = np.sum(totals, axis=1)
    plt.plot(months, total_per_month, color="black", label="Total", linewidth=2, linestyle="--")

    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    plt.title(f"Expenses Summary {year}")
    plt.ylabel("Total (€)", fontsize=12)
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


def show_expenses_pie(page: ft.Page, month: int | None = None) -> None:
    """Generates the plot showing a pie chart summary of the expenses."""
    logger.info("Called 'show_expenses_pie'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    if (profile := page.session.store.get("selected_profile")) is None:
        raise RuntimeError("Cannot retrieve the current profile.")

    # get data
    categories = np.array(fetch_categories(), dtype=str)
    totals = np.zeros((12, len(categories)), dtype=np.float32)
    for i, category in enumerate(categories):
        totals[:, i] = fetch_category(year, category, profile)

    if month is None:
        totals = totals.sum(axis=0)
    else:
        totals = totals[month - 1]

    # remove zeros
    mask = totals > 0
    totals = totals[mask]
    names = categories[mask]
    if not totals.size > 0:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("Empty monthly expenses"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    # plot
    fig = plt.figure()

    title = year if month is None else MONTHS[month - 1]
    plt.title(f"Expenses Pie Chart ({title})")
    patches, *_ = plt.pie(totals, labels=names, autopct="%1.1f%%")  # type: ignore

    legend_labels = [f"{cat}: € {format_amount(val)}" for cat, val in zip(names, totals)]
    plt.legend(
        patches,
        legend_labels,
        title="Expenses",
        title_fontproperties={"weight": "bold"},
        loc="center left",
        bbox_to_anchor=(1.2, 0, 0.5, 1),
    )

    fig.tight_layout()

    # show popup
    if page.width is None or page.height is None:
        raise RuntimeError("Cannot retrieve the page size.")

    chart = fch.MatplotlibChartWithToolbar(figure=fig, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    popup = ft.AlertDialog(
        content=ft.Container(
            chart,
            width=page.width * 0.9,
            height=page.height * 0.8,
        ),
        actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
    )

    page.show_dialog(popup)
    page.update()
