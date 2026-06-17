"""Implementation of the home layout."""

from logging import getLogger

import flet as ft

logger = getLogger("financial_tracker")


def home_view() -> ft.Control:
    """Implementation of the home view."""
    logger.info("Called 'home_view'")

    content = ft.Column(
        controls=[ft.Text("Home page: work in progress...")],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    return content
