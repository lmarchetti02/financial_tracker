"""Plots the diversification of portfolio holdings by issuer, region, currency, asset class, and detailed region."""

from logging import getLogger

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import ConnectionPatch

import database as db
from _helpers.formatting import enum_label, format_amount

from ._common import current_db_location

logger = getLogger("financial_tracker")

_UNLABELED_REGION = "Unlabeled"
_UNALLOCATED_REGION = "Unallocated"
_MAX_DIRECT_SLICES = 4


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


def build_kind_allocation_pie(kind_totals: dict[db.HoldingKind, float]) -> plt.Figure:
    """Builds a pie-chart figure of the portfolio's value broken down by `:enum:HoldingKind`.

    Unlike the other charts in this module, this doesn't show its own popup - it's meant to be
    embedded inside another dialog (the Portfolio page's asset-allocation tool), alongside the
    editable target-allocation form that dialog also shows.

    Args:
        kind_totals (dict[HoldingKind, float]): Total portfolio value per kind, e.g. as computed
            by `:meth:PortfolioView._compute_totals`. Must be non-empty.

    Returns:
        plt.Figure: The built pie chart.
    """
    names = sorted(kind_totals, key=lambda kind: kind_totals[kind], reverse=True)
    values = [kind_totals[name] for name in names]
    colors = [db.HOLDING_KIND_COLORS.get(name, "#808080") for name in names]
    labels = [enum_label(name) for name in names]

    fig, ax = plt.subplots(figsize=(5, 6.5))
    patches, *_ = ax.pie(values, colors=colors, autopct="%1.1f%%")  # type: ignore

    legend_labels = [f"{label}: € {format_amount(value, decimals=0)}" for label, value in zip(labels, values)]
    ax.legend(patches, legend_labels, loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=8)
    fig.tight_layout()

    return fig


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


def _build_bar_of_pie(totals: dict[str, float], title: str) -> plt.Figure:
    """Builds a "bar of pie" figure: the top regions as pie wedges, the rest broken into a bar.

    A plain pie with many small slivers reads as clutter, so once there's more than
    `:const:_MAX_DIRECT_SLICES` regions with value, only the biggest ones get their own wedge; the
    remainder are grouped into one exploded "Other" wedge, connected via lines to a stacked bar
    that breaks "Other" back down into its constituent regions. Falls back to a single plain pie
    when there aren't enough small regions to bother aggregating.
    """
    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)

    if len(sorted_items) <= _MAX_DIRECT_SLICES + 1:
        fig, ax = plt.subplots(figsize=(7, 6))
        _plot_pie(ax, title, totals)
        fig.tight_layout()
        return fig

    big_items = sorted_items[:_MAX_DIRECT_SLICES]
    small_items = sorted_items[_MAX_DIRECT_SLICES:]
    other_value = sum(value for _, value in small_items)

    # "Other" goes first: with `startangle` below, that centers its wedge at 0° (3 o'clock),
    # i.e. on the right, facing the bar it's connected to.
    pie_names = ["Other"] + [name for name, _ in big_items]
    pie_values = [other_value] + [value for _, value in big_items]
    colors = [plt.get_cmap("tab20")(i % 20) for i in range(len(pie_names))]
    explode = [0.1] + [0.0] * len(big_items)
    startangle = -180 * (other_value / sum(pie_values))

    fig = plt.figure(figsize=(11, 6))
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)

    wedges, *_ = ax1.pie(  # type: ignore
        pie_values, labels=pie_names, colors=colors, autopct="%1.1f%%", explode=explode, startangle=startangle
    )
    ax1.set_title(title)

    # break "Other" back down into a stacked bar, each region getting its own distinct color
    grand_total = sum(pie_values)
    bar_width = 0.3
    small_colors = [plt.get_cmap("tab20")((len(pie_names) + i) % 20) for i in range(len(small_items))]
    bottom = other_value
    for (name, value), color in zip(small_items, small_colors):
        bottom -= value
        ax2.bar(0, value, bar_width, bottom=bottom, color=color)
        # relative to the whole portfolio, matching the pie's own percentages - not just "Other"
        pct = value / grand_total * 100 if grand_total else 0
        ax2.text(
            bar_width / 2 + 0.05,
            bottom + value / 2,
            f"{name} {format_amount(pct, decimals=1)}%",
            va="center",
            ha="left",
            fontsize=8,
        )

    ax2.set_title("Other")
    ax2.axis("off")
    ax2.set_xlim(-2.5 * bar_width, 6 * bar_width)
    ax2.set_ylim(0, other_value)

    # connect the "Other" wedge (now on the right) to the bar with two lines, one per wedge edge
    other_wedge = wedges[0]
    theta1, theta2 = other_wedge.theta1, other_wedge.theta2
    center, r = other_wedge.center, other_wedge.r

    for theta, bar_y in ((theta2, other_value), (theta1, 0)):
        x = r * np.cos(np.deg2rad(theta)) + center[0]
        y = r * np.sin(np.deg2rad(theta)) + center[1]
        connection = ConnectionPatch(
            xyA=(-bar_width / 2, bar_y), coordsA=ax2.transData, xyB=(x, y), coordsB=ax1.transData
        )
        connection.set_color("gray")
        ax2.add_artist(connection)

    fig.tight_layout()
    return fig


def show_detailed_region_diversification(page: ft.Page) -> None:
    """Generates a bar-of-pie chart of the portfolio's value across the detailed region breakdown."""
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
    fig = _build_bar_of_pie(by_region, f"Detailed Diversification {location.year}")

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
