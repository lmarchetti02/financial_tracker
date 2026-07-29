"""Plots summaries of the incomes."""

from itertools import cycle
from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TABLEAU_COLORS

from _helpers.constants import MONTHS
from _helpers.formatting import format_amount
from database import fetch_income_totals, fetch_source, fetch_sources

from ._common import current_db_location

logger = getLogger("financial_tracker")


def show_income_summary(page: ft.Page, source: str | None = None) -> None:
    """Generates the plot showing a summary of the incomes, optionally filtered to one source."""
    logger.info("Called 'show_income_summary'")

    location = current_db_location(page)

    # get data
    sources = [source] if source is not None else fetch_sources()
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = np.zeros((len(months), len(sources)), dtype=np.float32)
    for i, src in enumerate(sources):
        totals[:, i] = fetch_source(location, src)

    # plot
    fig = plt.figure()

    linestyles = cycle(["-", "--", "-.", ":"])
    markers = cycle(["o", "s", "^", "D", "v", "p", "*"])
    colors = cycle(TABLEAU_COLORS)

    for i in range(len(sources)):
        plt.plot(
            months,
            totals[:, i],
            label=sources[i],
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
    plt.xlim(0.75, 12.25)

    title = f"Income Summary {location.year}"
    plt.title(title if source is None else f"{title} — {source}")
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


def show_income_trend(page: ft.Page) -> None:
    """Generates a line plot of total income by month, with the yearly average as a dotted reference line."""
    logger.info("Called 'show_income_trend'")

    location = current_db_location(page)

    # get data
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = fetch_income_totals(location)

    if not totals.any():
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("Empty monthly income"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    average = totals.mean()

    # plot
    fig = plt.figure()

    plt.axhline(average, linestyle=":", color="firebrick", linewidth=1.5, label=f"{location.year} average")
    plt.plot(months, totals, color="#006400", linewidth=1.2, alpha=0.4, label=str(location.year), zorder=1)
    plt.plot(months, totals, marker="o", linestyle="none", color="#006400", markersize=6, zorder=2)

    percent_of_average = (totals - average) / average * 100
    for month, value, pct in zip(months, totals, percent_of_average):
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

    plt.title(f"Income Trend {location.year}")
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


def show_income_pie(page: ft.Page, month: int | None = None) -> None:
    """Generates the plot showing a pie chart summary of the incomes."""
    logger.info("Called 'show_income_pie'")

    location = current_db_location(page)

    # get data
    sources = np.array(fetch_sources(), dtype=str)
    totals = np.zeros((12, len(sources)), dtype=np.float32)
    for i, source in enumerate(sources):
        totals[:, i] = fetch_source(location, source)

    if month is None:
        totals = totals.sum(axis=0)
    else:
        totals = totals[month - 1]

    # remove zeros
    mask = totals > 0
    totals = totals[mask]
    names = sources[mask]
    if not totals.size > 0:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("Empty monthly income"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    # plot
    fig = plt.figure()

    title = location.year if month is None else MONTHS[month - 1]
    plt.title(f"Income Pie Chart ({title})")
    patches, *_ = plt.pie(totals, labels=names, autopct="%1.1f%%")  # type: ignore

    legend_labels = [f"{src}: € {format_amount(val)}" for src, val in zip(names, totals)]
    plt.legend(
        patches,
        legend_labels,
        title="Income",
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
