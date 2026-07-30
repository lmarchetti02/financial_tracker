"""Plots the diversification of portfolio holdings by issuer, region, currency, and detailed region."""

from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt

import database as db
from _helpers.formatting import format_amount

from ._common import current_db_location

logger = getLogger("financial_tracker")

_UNLABELED_REGION = "Unlabeled"
_UNALLOCATED_REGION = "Unallocated"


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


def _region_totals(
    holdings: list[tuple[int, db.Holding]], region_allocations: dict[int, dict[str, float]]
) -> dict[str, float]:
    """Distributes each priced holding's value across its region breakdown, weighted by percentage.

    Any unallocated remainder (a holding with no breakdown, or one that doesn't add up to 100%) is
    bucketed under `:const:_UNALLOCATED_REGION`, so the total always matches the other two pies'.

    Args:
        holdings (list[tuple[int, `:class:Holding`]]): The holdings to aggregate.
        region_allocations (dict[int, dict[str, float]]): Each holding's `{region: percentage}`
            breakdown, as returned by `database.fetch_region_allocations`.

    Returns:
        dict[str, float]: Total value per region, skipping holdings with no fetched price yet.
    """
    totals: dict[str, float] = {}
    for holding_id, holding in holdings:
        value = db.compute_holding_value(holding)
        if value is None or value <= 0:
            continue

        allocations = region_allocations.get(holding_id, {})
        allocated_pct = sum(allocations.values())
        for region, pct in allocations.items():
            totals[region] = totals.get(region, 0.0) + value * pct / 100

        remainder = max(0.0, 100.0 - allocated_pct)
        if remainder > 0:
            totals[_UNALLOCATED_REGION] = totals.get(_UNALLOCATED_REGION, 0.0) + value * remainder / 100

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


def show_detailed_region_diversification(page: ft.Page) -> None:
    """Generates a pie chart of the portfolio's value across the detailed per-holding region breakdown."""
    logger.info("Called 'show_detailed_region_diversification'")

    location = current_db_location(page)

    # get data
    holdings = db.fetch_holdings(location)
    region_allocations = db.fetch_region_allocations(location)
    by_region = _region_totals(holdings, region_allocations)

    if not by_region:
        page.show_dialog(
            ft.AlertDialog(
                ft.Text("No detailed region breakdown entered yet"),
                actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
            )
        )
        page.update()
        return

    # plot
    fig, ax = plt.subplots(figsize=(7, 6))
    _plot_pie(ax, f"Detailed Diversification {location.year}", by_region)
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
