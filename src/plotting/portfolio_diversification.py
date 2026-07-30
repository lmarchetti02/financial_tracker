"""Plots the diversification of portfolio holdings by issuer, region, and currency."""

from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt

import database as db
from _helpers.formatting import format_amount

from ._common import current_db_location

logger = getLogger("financial_tracker")

_UNLABELED_REGION = "Unlabeled"


def _group_by_value(holdings: list[tuple[int, db.Holding]], key: str) -> dict[str, float]:
    """Sums each priced holding's market value into buckets keyed by one of its string fields.

    Args:
        holdings (list[tuple[int, `:class:Holding`]]): The holdings to group.
        key (str): The `:class:Holding` field to group by ("issuer", "region", or "currency").

    Returns:
        dict[str, float]: Total value per bucket, skipping holdings with no fetched price yet.
    """
    totals: dict[str, float] = {}
    for _, holding in holdings:
        value = db.compute_holding_value(holding)
        if value is None or value <= 0:
            continue

        bucket = getattr(holding, key) or _UNLABELED_REGION
        totals[bucket] = totals.get(bucket, 0.0) + value

    return totals


def _plot_pie(ax: plt.Axes, title: str, totals: dict[str, float]) -> None:
    """Draws one diversification pie chart, sorted by descending value, onto `ax`."""
    names = sorted(totals, key=lambda name: totals[name], reverse=True)
    values = [totals[name] for name in names]
    colors = [plt.get_cmap("tab20")(i % 20) for i in range(len(names))]

    patches, *_ = ax.pie(values, colors=colors, autopct="%1.1f%%")  # type: ignore
    ax.set_title(title)

    legend_labels = [f"{name}: € {format_amount(value, decimals=0)}" for name, value in zip(names, values)]
    ax.legend(patches, legend_labels, loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=8)


def show_portfolio_diversification(page: ft.Page) -> None:
    """Generates a side-by-side pie-chart breakdown of the portfolio's value by issuer, region, and currency."""
    logger.info("Called 'show_portfolio_diversification'")

    location = current_db_location(page)

    # get data
    holdings = db.fetch_holdings(location)
    by_issuer = _group_by_value(holdings, "issuer")
    by_region = _group_by_value(holdings, "region")
    by_currency = _group_by_value(holdings, "currency")

    if not by_issuer:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("No priced holdings yet"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    # plot
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    _plot_pie(axes[0], "Issuer", by_issuer)
    _plot_pie(axes[1], "Region", by_region)
    _plot_pie(axes[2], "Currency", by_currency)

    fig.suptitle(f"Portfolio Diversification {location.year}")
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
