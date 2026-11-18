"""The app-wide color standard: theme seed, page accents, semantic colors and the chart palette.

This is the only module that writes a color value. See `.claude/rules/ui_style.md` for when to use
which token. Every value is tuned for the light theme; the dark theme still uses them as-is.
"""

import flet as ft

from database import AccountKind, HoldingKind

# seeds the Material color scheme (default buttons, switches, focused fields, date pickers): a
# near-neutral slate, so default controls recede behind the page accents instead of looking like errors
SEED_COLOR = "#475569"

# secondary/hint text; theme-aware, so it stays readable in both light and dark mode
MUTED_COLOR = ft.Colors.ON_SURFACE_VARIANT

# text and icons drawn on top of an accent fill (table headers); every accent clears 4.5:1 against it
ON_ACCENT_COLOR = "#FFFFFF"

# one identity color per page: its table headers, section titles and chart/tool buttons
HOME_ACCENT = "#6D28D9"
EXPENSES_ACCENT = "#B91C1C"
INCOME_ACCENT = "#15803D"
TRANSFERS_ACCENT = "#1D4ED8"
ACCOUNTS_ACCENT = "#A16207"
PORTFOLIO_ACCENT = "#0F766E"

# for values that *mean* good/bad (gains vs. losses, saved vs. spent, an expired holding)
POSITIVE_COLOR = "#006300"
NEGATIVE_COLOR = "#C62828"

# the add button while it edits an existing row instead of adding a new one
EDIT_MODE_COLOR = "#B45309"

# the "Other" slice/line that folds a chart's smaller series together, and a lighter step of it for
# breaking "Other" down into alternating segments
NEUTRAL_COLOR = "#898781"
NEUTRAL_LIGHT_COLOR = "#c3c2b7"

# chart series identity, assigned in this fixed order and never cycled: past eight series, the rest
# fold into "Other". The order is what keeps neighboring series apart for color-blind readers.
CATEGORICAL_COLORS = (
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#6250d6",  # violet
    "#e34948",  # red
)
_BLUE, _ORANGE, _AQUA, _YELLOW, _MAGENTA, _GREEN, _VIOLET, _RED = CATEGORICAL_COLORS

# chart chrome
CHART_INK = "#0b0b0b"
CHART_SECONDARY_INK = "#52514e"
CHART_GRID_COLOR = "#e1e0d9"
CHART_BASELINE_COLOR = "#c3c2b7"
CHART_SURFACE_COLOR = "#FFFFFF"

# account/holding kinds, drawn as marks (icons, borders, chart fills) and never as text: some of
# these sit below 3:1 on white. Picked so the kinds that share a chart stay distinguishable in any
# order (pies sort by value) and so Crypto looks the same in both maps.
ACCOUNT_KIND_COLORS = {
    AccountKind.CASH: _GREEN,
    AccountKind.EMERGENCY: _BLUE,
    # not aqua: green and aqua are the closest pair this map could put on the most common kinds
    AccountKind.INVESTMENTS: _MAGENTA,
    AccountKind.CRYPTO: _YELLOW,
    AccountKind.PENSION: _VIOLET,
    AccountKind.DEBT: _RED,
    AccountKind.CREDIT: _AQUA,
}

HOLDING_KIND_COLORS = {
    HoldingKind.STOCKS: _BLUE,
    HoldingKind.BONDS: _GREEN,
    HoldingKind.COMMODITIES: _MAGENTA,
    HoldingKind.CRYPTO: _YELLOW,
    HoldingKind.FIXED_MATURITY_BOND: _AQUA,
}
