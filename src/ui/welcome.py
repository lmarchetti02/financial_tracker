"""Welcome page of the application."""

from collections.abc import Callable
from datetime import datetime
from logging import getLogger

import flet as ft

import database as db
from _helpers.constants import DEFAULT_PROFILE_NAME
from _helpers.formatting import parse_year, validate_profile_name

logger = getLogger("financial_tracker")


def welcome_page(page: ft.Page, on_start_callback: Callable[[int, str], None]) -> None:
    """Renders the welcome page.

    Args:
        page (ft.Page): The flet `Page` object.
        on_start_callback (Callable[[int, str], None]): A function that accepts the selected
            year and profile as input and produces no output.
    """
    logger.info("Called 'welcome_page'")

    last_selection = db.get_last_selection()
    default_year = last_selection[0] if last_selection is not None else datetime.today().year
    default_profile = last_selection[1] if last_selection is not None else DEFAULT_PROFILE_NAME

    def compute_hint() -> str:
        """Describes whether the currently typed year/profile is existing or new data."""
        try:
            year = parse_year(year_field.value or "")
            profile = validate_profile_name(profile_field.value or "")
        except ValueError:
            return ""

        if (year, profile) in db.list_year_profile_pairs():
            return f"'{profile}' already has data for {year} — it will be opened."
        return f"'{profile}' has no data for {year} yet — a new database will be created."

    def update_hint(_: ft.Event) -> None:
        """Clears field errors and updates the hint about whether this selection is new."""
        year_field.error_text = None
        profile_field.error_text = None
        hint_text.value = compute_hint()
        page.update()

    def start_app(_: ft.Event) -> None:
        """Validates the year/profile fields and, if valid, starts the app with them."""
        try:
            year = parse_year(year_field.value or "")
        except ValueError as error:
            year_field.error_text = str(error)
            page.update()
            return

        try:
            profile = validate_profile_name(profile_field.value or "")
        except ValueError as error:
            profile_field.error_text = str(error)
            page.update()
            return

        logger.debug(f"Year {year}, profile '{profile}' has been selected")

        # wipe page
        page.controls.clear()
        page.update()

        on_start_callback(year, profile)

    if page.height is None:
        raise RuntimeError("Cannot retrieve page height.")

    year_field = ft.TextField(label="Year", value=str(default_year), width=150, on_change=update_hint)
    profile_field = ft.TextField(label="Profile", value=default_profile, width=200, on_change=update_hint)
    hint_text = ft.Text(compute_hint(), size=12, color=ft.Colors.GREY)

    existing_pairs = sorted(db.list_year_profile_pairs())
    existing_text = (
        ft.Text(
            "Existing: " + ", ".join(f"{year} ({profile})" for year, profile in existing_pairs),
            size=12,
            color=ft.Colors.GREY,
        )
        if existing_pairs
        else None
    )

    layout = ft.Column(
        controls=[
            # title
            ft.Container(height=page.height * 0.1),
            ft.Text("FINANCIAL TRACKER", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("by Luca Marchetti", size=22),
            ft.Container(height=page.height * 0.2),
            # year/profile selection
            ft.Row(
                controls=[
                    year_field,
                    profile_field,
                    ft.Button("Start", on_click=start_app),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            hint_text,
            *([existing_text] if existing_text is not None else []),
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    page.add(layout)
