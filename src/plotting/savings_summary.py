"""Plots summaries of the net savings."""

from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np

from _helpers.constants import MONTHS
from database import fetch_expense_totals, fetch_income_totals

logger = getLogger("financial_tracker")


def show_savings_summary(page: ft.Page) -> None:
    """Generates the plot showing a summary of the net savings."""
    logger.info("Called 'show_savings_summary'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    # get data
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    net_savings = fetch_income_totals(year) - fetch_expense_totals(year)

    # plot
    fig = plt.figure()

    plt.axhline(0, color="black", linewidth=1)
    plt.fill_between(months, net_savings, 0, where=net_savings >= 0, color="green", alpha=0.3, interpolate=True)
    plt.fill_between(months, net_savings, 0, where=net_savings <= 0, color="red", alpha=0.3, interpolate=True)
    plt.plot(months, net_savings, marker="o", color="#8B8000", linewidth=2, markersize=6)

    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    plt.title(f"Savings Summary {year}")
    plt.ylabel("Net Savings (€)", fontsize=12)

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


def show_savings_pie(page: ft.Page) -> None:
    """Generates the plot showing how much of the year's income was saved versus spent."""
    logger.info("Called 'show_savings_pie'")

    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    # get data
    total_income = fetch_income_totals(year).sum()
    total_expenses = fetch_expense_totals(year).sum()
    total_saved = total_income - total_expenses

    values = np.array([total_saved, total_expenses], dtype=np.float32)
    names = np.array(["Saved", "Spent"], dtype=str)

    # remove non-positive slices (e.g. a deficit year has nothing "saved" to show)
    mask = values > 0
    values = values[mask]
    names = names[mask]
    if not values.size > 0:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("Empty yearly income"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    # plot
    fig = plt.figure()

    color_map = {"Saved": "darkgreen", "Spent": "firebrick"}
    colors = [color_map[name] for name in names]

    plt.title(f"Savings Pie Chart ({year})")
    patches, *_ = plt.pie(values, labels=names, colors=colors, autopct="%1.1f%%")  # type: ignore

    legend_labels = [f"{name}: € {val:.2f}" for name, val in zip(names, values)]
    plt.legend(
        patches,
        legend_labels,
        title="Savings",
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
