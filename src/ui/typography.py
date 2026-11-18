"""The app-wide typography standard: font family, size scale and text builders.

See `.claude/rules/ui_style.md` for when to use which role.
"""

from pathlib import Path
from typing import Any

import flet as ft

FONT_FAMILY = "JetBrains Mono"
# relative to the Flet assets directory (`src/assets`), as `page.fonts` expects. The variable-weight
# file is used so bold is drawn from the font's own bold instance rather than synthesized.
FONT_ASSET = "fonts/JetBrainsMono-Variable.ttf"
# the same fonts on disk, for consumers that need a real file path (matplotlib)
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

PAGE_TITLE_SIZE = 30
SECTION_SIZE = 20
SUBHEADING_SIZE = 16
BODY_SIZE = 14
CAPTION_SIZE = 12

# secondary/hint text; theme-aware, so it stays readable in both light and dark mode
MUTED_COLOR = ft.Colors.ON_SURFACE_VARIANT

# for `heading_text_style`-like parameters that take a style rather than a control (table headings)
HEADING_TEXT_STYLE = ft.TextStyle(size=SUBHEADING_SIZE, weight=ft.FontWeight.BOLD)


def build_theme() -> ft.Theme:
    """Builds the app theme, mapping every Material text slot onto the size scale.

    Material controls pick their text style from these slots (dialog titles use `headline_small`,
    text fields `body_large`, buttons `label_large`, ...), so mapping them all keeps text the app
    doesn't style explicitly on the same scale.

    A custom text theme *replaces* Material's default styles rather than merging into them, so each
    slot has to restate the text color and family too: without a color, unstyled text falls back to
    white, which is invisible in light mode. `ON_SURFACE` is resolved per theme, so it stays dark
    on light and light on dark.
    """

    def slot(size: int, bold: bool = False) -> ft.TextStyle:
        """Builds one text-theme slot on the scale, in the theme's text color and the app font."""
        weight = ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL
        return ft.TextStyle(size=size, weight=weight, color=ft.Colors.ON_SURFACE, font_family=FONT_FAMILY)

    page_title = slot(PAGE_TITLE_SIZE, bold=True)
    section = slot(SECTION_SIZE, bold=True)
    subheading_style = slot(SUBHEADING_SIZE, bold=True)
    body = slot(BODY_SIZE)
    caption_style = slot(CAPTION_SIZE)

    text_theme = ft.TextTheme(
        display_large=page_title,
        display_medium=page_title,
        display_small=page_title,
        headline_large=page_title,
        headline_medium=section,
        headline_small=section,
        title_large=subheading_style,
        title_medium=subheading_style,
        title_small=subheading_style,
        body_large=body,
        body_medium=body,
        label_large=body,
        body_small=caption_style,
        label_medium=caption_style,
        label_small=caption_style,
    )
    return ft.Theme(color_scheme_seed=ft.Colors.RED, font_family=FONT_FAMILY, text_theme=text_theme)


def page_title(text: str, **kwargs: Any) -> ft.Text:
    """Builds a page title: the topmost heading of a view (30, bold)."""
    return ft.Text(text, size=PAGE_TITLE_SIZE, weight=ft.FontWeight.BOLD, **kwargs)


def section_title(text: str, color: str | None = None, **kwargs: Any) -> ft.Text:
    """Builds a section heading inside a view (20, bold), optionally in the view's accent color."""
    return ft.Text(text, size=SECTION_SIZE, weight=ft.FontWeight.BOLD, color=color, **kwargs)


def subheading(text: str, **kwargs: Any) -> ft.Text:
    """Builds a subheading: a group label, a setting's name, a summary line (16, bold)."""
    return ft.Text(text, size=SUBHEADING_SIZE, weight=ft.FontWeight.BOLD, **kwargs)


def caption(text: str = "", color: str | None = MUTED_COLOR, **kwargs: Any) -> ft.Text:
    """Builds a caption: a hint, subtitle or small status line (12), muted unless `color` is given."""
    return ft.Text(text, size=CAPTION_SIZE, color=color, **kwargs)
