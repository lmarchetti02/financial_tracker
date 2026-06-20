"""Welcome page of the application."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

logger = getLogger("financial_tracker")


YEAR_OPTIONS = [ft.dropdown.Option("2026")]


def welcome_page(page: ft.Page, on_start_callback: Callable[[int], None]) -> None:
    """Renders the welcome page.

    Args:
        page (ft.Page): The flet `Page` object.
        on_start_callback (Callable[[int], None]): A function that accepts the year
            as input and produces no output.
    """
    logger.info("Called 'welcome_page'")

    def clear_error(_: ft.Event) -> None:
        """Clears the error text of the drop-down menu."""
        years_dropdown.error_text = None
        page.update()

    def start_app(_: ft.Event) -> None:
        """Clears the welcome page and checks the selected year."""
        if years_dropdown.value is None:
            years_dropdown.error_text = "You have to select a year"
            page.update()
            return

        selected_year = int(years_dropdown.value)
        logger.debug(f"Year {selected_year} has been selected")

        # wipe page
        page.controls.clear()
        page.update()

        on_start_callback(selected_year)

    if page.window.height is None:
        raise RuntimeError("Cannot retrieve page height.")

    years_dropdown = ft.Dropdown(
        label="Select year",
        value="2026",
        width=150,
        options=YEAR_OPTIONS,
        on_text_change=clear_error,
    )

    layout = ft.Column(
        controls=[
            # title
            ft.Container(height=page.window.height * 0.1),
            ft.Text("FINANCIAL TRACKER", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("by Luca Marchetti", size=22),
            ft.Container(height=page.window.height * 0.2),
            # year selection
            ft.Row(
                controls=[
                    years_dropdown,
                    ft.Button("Start", on_click=start_app),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    page.add(layout)
