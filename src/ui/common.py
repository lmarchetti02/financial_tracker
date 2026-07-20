"""Shared UI helpers used across views."""

import flet as ft


def show_alert(page: ft.Page, title: str, content: str) -> None:
    """Shows alert for missing data.

    Args:
        page (ft.Page): The page object.
        title (str): The title of the alert dialog.
        content (str): The content of the alert dialog.
    """
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(content),
            actions=[ft.TextButton("Dismiss", on_click=lambda _: page.pop_dialog())],
        )
    )
    page.update()
