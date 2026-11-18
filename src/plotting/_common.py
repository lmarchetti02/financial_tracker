"""Private helpers shared across the plotting modules."""

from collections.abc import Callable
from itertools import cycle

import flet as ft
import flet_charts as fch
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.figure import Figure

from _helpers.constants import MONTHS
from _helpers.formatting import format_amount
from database import DbLocation
from ui.common import current_db_location as current_db_location
from ui.colors import (CATEGORICAL_COLORS, CHART_BASELINE_COLOR, CHART_GRID_COLOR, CHART_INK,
                       CHART_SECONDARY_INK, CHART_SURFACE_COLOR, NEGATIVE_COLOR, NEUTRAL_COLOR, POSITIVE_COLOR)
from ui.typography import FONT_FAMILY, FONTS_DIR

type GroupedTotalsFetcher = Callable[[DbLocation], dict[str, np.ndarray]]

# the chart text scale (points); the UI's scale lives in `ui.typography`
CHART_TITLE_SIZE = 14
CHART_LABEL_SIZE = 12
CHART_TICK_SIZE = 10
CHART_ANNOTATION_SIZE = 8

# a chart never needs more colors than the categorical palette has: the smallest series fold into "Other"
MAX_SERIES = len(CATEGORICAL_COLORS)

# a surface-colored ring around each pie wedge, so neighboring wedges stay apart
PIE_WEDGE_PROPS = {"edgecolor": CHART_SURFACE_COLOR, "linewidth": 2}


def _configure_style() -> None:
    """Draws every chart in the app's font and colors, on the chart text scale.

    matplotlib needs the static Regular/Bold files: it doesn't pick weights out of a variable font.
    """
    for font_file in ("JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf"):
        font_manager.fontManager.addfont(FONTS_DIR / font_file)

    plt.rcParams.update(
        {
            "font.family": FONT_FAMILY,
            "font.size": CHART_TICK_SIZE,
            "axes.titlesize": CHART_TITLE_SIZE,
            "axes.titleweight": "bold",
            "figure.titlesize": CHART_TITLE_SIZE,
            "figure.titleweight": "bold",
            "axes.labelsize": CHART_LABEL_SIZE,
            "xtick.labelsize": CHART_TICK_SIZE,
            "ytick.labelsize": CHART_TICK_SIZE,
            "legend.fontsize": CHART_ANNOTATION_SIZE,
            "figure.facecolor": CHART_SURFACE_COLOR,
            "axes.facecolor": CHART_SURFACE_COLOR,
            "axes.prop_cycle": plt.cycler(color=CATEGORICAL_COLORS),
            "axes.edgecolor": CHART_BASELINE_COLOR,
            "axes.labelcolor": CHART_INK,
            "axes.titlecolor": CHART_INK,
            "text.color": CHART_INK,
            "xtick.color": CHART_SECONDARY_INK,
            "ytick.color": CHART_SECONDARY_INK,
            "grid.color": CHART_GRID_COLOR,
        }
    )


# every chart module imports this one, so this runs before any figure is drawn
_configure_style()


def fold_into_other(names: list[str], values: np.ndarray) -> tuple[list[str], np.ndarray, list[str]]:
    """Ranks series by total, keeps the largest ones and sums the rest into one "Other" series.

    Series are ranked largest first and colored in that order from `CATEGORICAL_COLORS`. With more
    series than the palette has colors, the smallest ones are summed into a final "Other (n)" series
    drawn in `NEUTRAL_COLOR`, so no color is ever reused or generated.

    Args:
        names (list[str]): The name of each series.
        values (np.ndarray): The series' values, one per series along the last axis: shape `(n,)`
            for a pie, `(12, n)` for monthly lines.

    Returns:
        tuple[list[str], np.ndarray, list[str]]: The kept names, their values (same layout as
            `values`, possibly with fewer series) and one color per kept series.
    """
    weights = values.reshape(-1, len(names)).sum(axis=0)
    order = sorted(range(len(names)), key=lambda i: weights[i], reverse=True)

    if len(order) <= MAX_SERIES:
        return [names[i] for i in order], values[..., order], list(CATEGORICAL_COLORS[: len(order)])

    kept, rest = order[: MAX_SERIES - 1], order[MAX_SERIES - 1 :]
    folded_names = [names[i] for i in kept] + [f"Other ({len(rest)})"]
    folded_values = np.concatenate([values[..., kept], values[..., rest].sum(axis=-1, keepdims=True)], axis=-1)
    colors = list(CATEGORICAL_COLORS[: len(kept)]) + [NEUTRAL_COLOR]
    return folded_names, folded_values, colors


def _totals_matrix(location: DbLocation, options: list[str], fetch_all: GroupedTotalsFetcher) -> np.ndarray:
    """Builds a (12, len(options)) matrix of monthly totals, with a zero column for an entry with no data."""
    by_option = fetch_all(location)
    totals = np.zeros((12, len(options)), dtype=np.float32)
    for i, option in enumerate(options):
        if option in by_option:
            totals[:, i] = by_option[option]
    return totals


class FigureClosingChart(fch.MatplotlibChart):
    """A `MatplotlibChart` that releases its figure from pyplot once the chart leaves the page."""

    def will_unmount(self) -> None:
        """Runs the chart's own cleanup, then closes the figure.

        The order matters: `plt.close` swaps in a canvas whose `manager` is `None`, and the parent's
        `will_unmount` still needs that manager to unregister the chart.
        """
        super().will_unmount()
        plt.close(self.figure)


class FigureClosingChartWithToolbar(fch.MatplotlibChartWithToolbar):
    """A `MatplotlibChartWithToolbar` whose inner chart is a `:class:FigureClosingChart`."""

    def build(self) -> None:  # noqa: D102
        super().build()
        # the toolbar's buttons look `self.mpl` up when clicked, so swapping it here rewires them too
        self.mpl = FigureClosingChart(
            figure=self.figure,
            expand=True,
            on_message=self.on_message,
            on_toolbar_buttons_update=self.on_toolbar_update,
        )
        self.controls[-1] = self.mpl


def show_chart_popup(page: ft.Page, fig: Figure) -> None:
    """Shows `fig` in a popup sized relative to the page, with a "Close" button.

    Args:
        page (ft.Page): The page object.
        fig (Figure): The figure to show.

    Raises:
        RuntimeError: If the page size can't be retrieved.
    """
    if page.width is None or page.height is None:
        raise RuntimeError("Cannot retrieve the page size.")

    chart = FigureClosingChartWithToolbar(figure=fig, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    popup = ft.AlertDialog(
        content=ft.Container(chart, width=page.width * 0.9, height=page.height * 0.8),
        actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
    )

    page.show_dialog(popup)
    page.update()


def show_empty_popup(page: ft.Page, message: str) -> None:
    """Shows a small popup telling the user there's nothing to plot.

    Args:
        page (ft.Page): The page object.
        message (str): The text to show.
    """
    page.show_dialog(
        ft.AlertDialog(
            ft.Text(message),
            actions=[ft.Button("Close", on_click=lambda _: page.pop_dialog())],
        )
    )
    page.update()


def show_lookup_summary(
    page: ft.Page,
    name: str,
    selected: str | None,
    fetch_options: Callable[[], list[str]],
    fetch_all: GroupedTotalsFetcher,
) -> None:
    """Plots one line per lookup entry (e.g. per category) of its monthly totals.

    Args:
        page (ft.Page): The page object.
        name (str): The plotted domain, used in the title (e.g. "Expenses").
        selected (str | None): A single entry to plot, or `None` to plot every entry.
        fetch_options (Callable[[], list[str]]): Returns every entry of the lookup list.
        fetch_all (GroupedTotalsFetcher): Returns the monthly totals of every entry with data.
    """
    location = current_db_location(page)

    # get data
    options = [selected] if selected is not None else fetch_options()
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = _totals_matrix(location, options, fetch_all)
    options, totals, colors = fold_into_other(options, totals)

    # plot
    fig = plt.figure()

    # line style and marker are a second channel besides color, for lines that cross
    linestyles = cycle(["-", "--", "-.", ":"])
    markers = cycle(["o", "s", "^", "D", "v", "p", "*"])

    for i in range(len(options)):
        plt.plot(
            months,
            totals[:, i],
            label=options[i],
            linestyle=next(linestyles),
            marker=next(markers),
            color=colors[i],
            linewidth=2,
            markersize=6,
            alpha=0.8,
        )

    plt.grid(axis="y", linestyle="--")
    plt.grid(axis="x", linestyle="--")
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    title = f"{name} Summary {location.year}"
    plt.title(title if selected is None else f"{title} — {selected}")
    plt.ylabel("Total (€)")
    plt.legend()

    fig.tight_layout()

    show_chart_popup(page, fig)


def show_monthly_trend(
    page: ft.Page,
    name: str,
    fetch_totals: Callable[[DbLocation], np.ndarray],
    color: str,
    empty_text: str,
    lower_is_better: bool,
) -> None:
    """Plots the monthly totals, with the yearly average as a dotted reference line.

    Args:
        page (ft.Page): The page object.
        name (str): The plotted domain, used in the title (e.g. "Expenses").
        fetch_totals (Callable[[DbLocation], np.ndarray]): Returns the monthly totals.
        color (str): The color of the line and its markers: the page's accent.
        empty_text (str): The text shown instead of the chart when every month is zero.
        lower_is_better (bool): Whether a month below the average is annotated as good
            (`POSITIVE_COLOR`, expenses) rather than as bad (`NEGATIVE_COLOR`, income).
    """
    location = current_db_location(page)

    # get data
    months = np.array([i + 1 for i in range(12)], dtype=np.uint8)
    totals = fetch_totals(location)

    if not totals.any():
        show_empty_popup(page, empty_text)
        return

    average = totals.mean()

    # plot
    fig = plt.figure()

    plt.axhline(average, linestyle=":", color=CHART_SECONDARY_INK, linewidth=1.5, label=f"{location.year} average")
    plt.plot(months, totals, color=color, linewidth=1.2, alpha=0.4, label=str(location.year), zorder=1)
    plt.plot(months, totals, marker="o", linestyle="none", color=color, markersize=6, zorder=2)

    percent_of_average = (totals - average) / average * 100
    for month, value, pct in zip(months, totals, percent_of_average):
        is_good = pct <= 0 if lower_is_better else pct >= 0
        plt.annotate(
            f"{pct:+.1f}%",
            (month, value),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=CHART_ANNOTATION_SIZE,
            color=POSITIVE_COLOR if is_good else NEGATIVE_COLOR,
        )

    plt.grid(axis="y", linestyle="--")
    plt.grid(axis="x", linestyle="--")
    plt.xticks(months, MONTHS)
    plt.xlim(0.75, 12.25)

    plt.title(f"{name} Trend {location.year}")
    plt.ylabel("Total (€)")
    plt.legend()

    fig.tight_layout()

    show_chart_popup(page, fig)


def show_lookup_pie(
    page: ft.Page,
    name: str,
    month: int | None,
    fetch_options: Callable[[], list[str]],
    fetch_all: GroupedTotalsFetcher,
    empty_text: str,
) -> None:
    """Plots a pie chart of the totals per lookup entry, for the whole year or one month.

    Args:
        page (ft.Page): The page object.
        name (str): The plotted domain, used in the title and the legend title (e.g. "Expenses").
        month (int | None): The month to plot, or `None` for the whole year.
        fetch_options (Callable[[], list[str]]): Returns every entry of the lookup list.
        fetch_all (GroupedTotalsFetcher): Returns the monthly totals of every entry with data.
        empty_text (str): The text shown instead of the chart when there is nothing to plot.
    """
    location = current_db_location(page)

    # get data
    option_names = fetch_options()
    options = np.array(option_names, dtype=str)
    totals = _totals_matrix(location, option_names, fetch_all)

    if month is None:
        totals = totals.sum(axis=0)
    else:
        totals = totals[month - 1]

    # remove zeros
    mask = totals > 0
    totals = totals[mask]
    names = options[mask]
    if not totals.size > 0:
        show_empty_popup(page, empty_text)
        return
    names, totals, colors = fold_into_other(names.tolist(), totals)

    # plot
    fig = plt.figure()

    title = location.year if month is None else MONTHS[month - 1]
    plt.title(f"{name} Pie Chart ({title})")
    patches, *_ = plt.pie(  # type: ignore
        totals, labels=names, colors=colors, autopct="%1.1f%%", wedgeprops=PIE_WEDGE_PROPS
    )

    legend_labels = [f"{option}: € {format_amount(val)}" for option, val in zip(names, totals)]
    plt.legend(
        patches,
        legend_labels,
        title=name,
        title_fontproperties={"weight": "bold"},
        loc="center left",
        bbox_to_anchor=(1.2, 0, 0.5, 1),
    )

    fig.tight_layout()

    show_chart_popup(page, fig)
