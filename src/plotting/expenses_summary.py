"""Plots summaries of the expenses."""

from itertools import cycle
from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TABLEAU_COLORS

from database.expenses import Categories, fetch_category
from helpers.constants import MONTHS

logger = getLogger("financial_tracker")

CAT_NAMES = np.array([cat.name.capitalize().replace("_", " ") for cat in Categories], dtype=str)


def show_expenses_summary(page: ft.Page) -> None:
    """Generates the plot showing a summary of the expenses."""
    logger.info("Called 'show_expenses_summary'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    # get data
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = np.zeros((len(months), len(Categories)), dtype=np.float32)
    for i, category in enumerate(Categories):
        totals[:, i] = fetch_category(year, category)

    # plot
    fig = plt.figure()

    linestyles = cycle(["-", "--", "-.", ":"])
    markers = cycle(["o", "s", "^", "D", "v", "p", "*"])
    colors = cycle(TABLEAU_COLORS)

    for i in range(len(Categories)):
        plt.plot(
            months,
            totals[:, i],
            label=CAT_NAMES[i],
            linestyle=next(linestyles),
            marker=next(markers),
            color=next(colors),
            linewidth=2,
            markersize=6,
            alpha=0.8,
        )

    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    plt.xticks(months, MONTHS)
    plt.xlim(0, 13)

    plt.title(f"Expenses Summary {year}")
    plt.ylabel("Total (€)", fontsize=12)
    plt.legend()

    fig.tight_layout()

    # show popup
    if page.window.width is None or page.window.height is None:
        raise RuntimeError("Cannot retrieve the window size.")

    chart = fch.MatplotlibChartWithToolbar(figure=fig, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    popup = ft.AlertDialog(
        content=ft.Container(chart, width=page.window.width * 0.9, height=page.window.height * 0.8),
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

    # get data
    totals = np.zeros((12, len(Categories)), dtype=np.float32)
    for i, category in enumerate(Categories):
        totals[:, i] = fetch_category(year, category)

    if month is None:
        totals = totals.sum(axis=0)
    else:
        totals = totals[month - 1]

    # remove zeros
    mask = totals > 0
    totals = totals[mask]
    names = CAT_NAMES[mask]
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

    legend_labels = [f"{cat}: € {val:.2f}" for cat, val in zip(names, totals)]
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
    if page.window.width is None or page.window.height is None:
        raise RuntimeError("Cannot retrieve the window size.")

    chart = fch.MatplotlibChartWithToolbar(figure=fig, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    popup = ft.AlertDialog(
        content=ft.Container(
            chart,
            width=page.window.width * 0.9,
            height=page.window.height * 0.8,
        ),
        actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
    )

    page.show_dialog(popup)
    page.update()
