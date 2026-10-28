"""Plots the allocation of account balances across account kinds."""

from logging import getLogger

import flet as ft
import matplotlib.pyplot as plt
import numpy as np

from _helpers.constants import MONTHS
from _helpers.formatting import enum_label, format_amount
from database import ACCOUNT_KIND_COLORS, AccountKind, DbLocation, fetch_balances_by_kind

from ._common import current_db_location, show_chart_popup, show_empty_popup

logger = getLogger("financial_tracker")

_DEFAULT_COLOR = "#808080"
_EXCLUDED_KINDS = {AccountKind.PENSION, AccountKind.CREDIT, AccountKind.DEBT}


def _fetch_allocation_totals(location: DbLocation) -> dict[AccountKind, np.ndarray]:
    """Fetches per-kind monthly totals for asset allocation, excluding `_EXCLUDED_KINDS`."""
    return {kind: totals for kind, totals in fetch_balances_by_kind(location).items() if kind not in _EXCLUDED_KINDS}


def show_asset_allocation_summary(page: ft.Page) -> None:
    """Generates a 100% stacked area chart of each account kind's share of the total, per month."""
    logger.info("Called 'show_asset_allocation_summary'")

    location = current_db_location(page)

    # get data
    totals_by_kind = _fetch_allocation_totals(location)
    if not totals_by_kind:
        show_empty_popup(page, "No balances logged yet")
        return

    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    kinds = sorted(totals_by_kind, key=lambda k: k.name)
    stacked = np.stack([totals_by_kind[kind] for kind in kinds])
    monthly_total = stacked.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        percentages = np.where(monthly_total > 0, stacked / monthly_total * 100, 0)

    # plot
    fig = plt.figure()

    colors = [ACCOUNT_KIND_COLORS.get(kind, _DEFAULT_COLOR) for kind in kinds]
    labels = [enum_label(kind) for kind in kinds]
    plt.stackplot(months, percentages, labels=labels, colors=colors, alpha=0.85)

    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.xticks(months, MONTHS)
    plt.xlim(1, 12)
    plt.ylim(0, 100)

    plt.title(f"Asset Allocation {location.year}")
    plt.ylabel("Share of total balance (%)", fontsize=12)
    plt.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))

    fig.tight_layout()

    show_chart_popup(page, fig)


def show_asset_allocation_pie(page: ft.Page) -> None:
    """Generates a pie chart of the last month with any logged balance, split by account kind."""
    logger.info("Called 'show_asset_allocation_pie'")

    location = current_db_location(page)

    # get data
    totals_by_kind = _fetch_allocation_totals(location)
    if not totals_by_kind:
        show_empty_popup(page, "No balances logged yet")
        return

    kinds = sorted(totals_by_kind, key=lambda k: k.name)
    stacked = np.stack([totals_by_kind[kind] for kind in kinds])
    monthly_total = stacked.sum(axis=0)
    nonzero_months = np.nonzero(monthly_total)[0]
    if nonzero_months.size == 0:
        show_empty_popup(page, "No balances logged yet")
        return
    month = int(nonzero_months[-1]) + 1

    values = stacked[:, month - 1]
    mask = values > 0
    values = values[mask]
    kinds = [kind for kind, keep in zip(kinds, mask) if keep]

    names = [enum_label(kind) for kind in kinds]
    colors = [ACCOUNT_KIND_COLORS.get(kind, _DEFAULT_COLOR) for kind in kinds]

    # plot
    fig = plt.figure()

    plt.title(f"Asset Allocation ({MONTHS[month - 1]} {location.year})")
    patches, *_ = plt.pie(values, labels=names, colors=colors, autopct="%1.1f%%")  # type: ignore

    legend_labels = [f"{name}: € {format_amount(val, decimals=0)}" for name, val in zip(names, values)]
    plt.legend(
        patches,
        legend_labels,
        title="Kind",
        title_fontproperties={"weight": "bold"},
        loc="center left",
        bbox_to_anchor=(1.2, 0, 0.5, 1),
    )

    fig.tight_layout()

    show_chart_popup(page, fig)
