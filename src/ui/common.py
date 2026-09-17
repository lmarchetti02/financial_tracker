"""Shared UI helpers used across views."""

from typing import ClassVar

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db


class CollapsibleFormMixin:
    """Shared expand/collapse behavior for a view's add/edit form, hidden until toggled open.

    A host class must build `self.form_content` (the `ft.Column` of input fields) and call
    `_init_collapsible_form()` right after, and must implement `clear_inputs()`/`reset_add_button()`
    (both `:class:BaseCrudView` and `:class:PortfolioView` already do, independently).
    """

    _item_label: ClassVar[str]
    _form_height: ClassVar[int] = 240

    def _init_collapsible_form(self) -> None:
        """Wraps `self.form_content` in a `form_container` and builds the `toggle_form_button`."""
        self._form_expanded = False
        self.toggle_form_button = ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE, tooltip=f"Add {self._item_label}", on_click=self.toggle_form
        )
        self.form_container = ft.Container(
            content=self.form_content,
            height=0,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    def toggle_form(self, _: ft.Event) -> None:
        """Expands or collapses the add/edit form, animating the transition."""
        if not self._form_expanded:
            self.clear_inputs()
            self.reset_add_button()
        self._set_form_expanded(not self._form_expanded)
        self._page.update()

    def _set_form_expanded(self, expanded: bool) -> None:
        """Sets whether the add/edit form is shown, without pushing the change to the page."""
        self._form_expanded = expanded
        self.form_container.height = self._form_height if expanded else 0
        self.toggle_form_button.icon = ft.Icons.EXPAND_LESS if expanded else ft.Icons.ADD_CIRCLE_OUTLINE
        self.toggle_form_button.tooltip = "Hide form" if expanded else f"Add {self._item_label}"


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
