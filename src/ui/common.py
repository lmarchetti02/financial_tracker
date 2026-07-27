"""Shared UI helpers used across views."""

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db


def current_db_location(page: ft.Page) -> db.DbLocation:
    """Reads the currently selected year/profile from `page.session.store`.

    Args:
        page (ft.Page): The page object.

    Returns:
        `:class:database.DbLocation`: The selected year/profile.

    Raises:
        RuntimeError: If either hasn't been set yet.
    """
    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retrieve the current year.")

    if (profile := page.session.store.get("selected_profile")) is None:
        raise RuntimeError("Cannot retrieve the current profile.")

    return db.DbLocation(int(year), profile)


def build_styled_data_table(columns: list[DataColumn2], rows: list[ft.DataRow], heading_color: str) -> DataTable2:
    """Builds a `:class:DataTable2` styled consistently with every other table in the app.

    Args:
        columns (list[DataColumn2]): The columns of the table.
        rows (list[ft.DataRow]): The rows of the table.
        heading_color (str): The background color of the heading row.

    Returns:
        DataTable2: The styled table.
    """
    borders = ft.BorderSide(width=2)
    v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

    return DataTable2(
        fixed_top_rows=1,
        border=ft.Border(top=borders, bottom=borders, right=borders, left=borders),
        vertical_lines=v_lines,
        horizontal_lines=v_lines,
        heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
        heading_row_color=heading_color,
        sort_arrow_icon_color=ft.Colors.WHITE,
        heading_row_height=35,
        horizontal_margin=10,
        column_spacing=15,
        columns=columns,  # type: ignore
        rows=rows,
    )


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
