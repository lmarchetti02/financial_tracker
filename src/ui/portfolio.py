"""Implementation of the portfolio layout."""

from logging import getLogger

import flet as ft

logger = getLogger("financial_tracker")


def portfolio_view() -> ft.Control:
    """Implementation of the portfolio view."""
    logger.info("Called 'porfolio_view'")

    content = ft.Column(
        controls=[ft.Text("Porfolio page: work in progress...")],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    return content
