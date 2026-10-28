"""Shared UI helpers used across views."""

from collections.abc import Callable
from typing import Any, ClassVar

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db

FILTER_ACTIVE_COLOR = ft.Colors.AMBER_700

# Flet's date pickers have no first-day-of-week option: Flutter takes it from the locale, and the
# app's default `en_US` starts weeks on Sunday. `en_GB` keeps English labels but starts on Monday.
DATE_PICKER_LOCALE = ft.Locale("en", "GB")


def sync_filter_menu(
    menu: ft.PopupMenuButton, active_label: str | None, inactive_color: str, inactive_tooltip: str
) -> None:
    """Colors a filter popup menu's icon and updates its tooltip to reflect whether a filter is set.

    Args:
        menu (ft.PopupMenuButton): The filter menu to restyle in place.
        active_label (str | None): The value currently filtered on, or `None` when the filter is cleared.
        inactive_color (str): The icon color to restore when no filter is set.
        inactive_tooltip (str): The tooltip to restore when no filter is set.
    """
    menu.icon_color = inactive_color if active_label is None else FILTER_ACTIVE_COLOR
    menu.tooltip = inactive_tooltip if active_label is None else f"Showing {active_label} only"


class CollapsibleFormMixin:
    """Shared expand/collapse behavior for a view's add/edit form, hidden until toggled open.

    A host class must build its add button with `_build_add_button()`, build `self.form_content`
    (the `ft.Column` of input fields) and call `_init_collapsible_form()` right after, and must
    implement `clear_inputs()` (both `:class:BaseCrudView` and `:class:PortfolioView` do). The
    add button's "Add ..."/"Edit ..." modes and the "Clear Fields" button are shared here.
    """

    _item_label: ClassVar[str]
    _form_height: ClassVar[int] = 240

    def _build_add_button(self, on_add: Callable[[ft.Event], None]) -> ft.Button:
        """Builds the form's "Add ..." button, remembering `on_add` for `reset_add_button()`."""
        self._on_add = on_add
        self.add_button = ft.Button(f"Add {self._item_label}", on_click=on_add)
        return self.add_button

    def _enter_edit_mode(self, on_modify: Callable[[ft.Event], None]) -> None:
        """Turns the add button into an "Edit ..." button that calls `on_modify`."""
        self.add_button.content = f"Edit {self._item_label}"
        self.add_button.color = ft.Colors.PURPLE
        self.add_button.on_click = on_modify

    def reset_add_button(self) -> None:
        """Resets the add button to its base "Add ..." label, color, and click handler."""
        self.add_button.content = f"Add {self._item_label}"
        self.add_button.color = None
        self.add_button.on_click = self._on_add

    def _build_clear_button(self) -> ft.Button:
        """Builds the "Clear Fields" button shared by every host."""
        return ft.Button("Clear Fields", on_click=self._handle_clear_click)

    def _handle_clear_click(self, _: ft.Event) -> None:
        """Clears the add-item inputs, resets the add button, and pushes the change to the page."""
        self.clear_inputs()
        self.reset_add_button()
        self._page.update()

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
            on_animation_end=self._on_form_animation_end,
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
        # clip only while the height animates: once fully open, the floating labels of the first row's
        # fields poke out above the container's top edge and would otherwise be cut off
        if expanded != self._form_expanded:
            self.form_container.clip_behavior = ft.ClipBehavior.HARD_EDGE
        self._form_expanded = expanded
        self.form_container.height = self._form_height if expanded else 0
        self.toggle_form_button.icon = ft.Icons.EXPAND_LESS if expanded else ft.Icons.ADD_CIRCLE_OUTLINE
        self.toggle_form_button.tooltip = "Hide form" if expanded else f"Add {self._item_label}"

    def _on_form_animation_end(self, _: ft.Event) -> None:
        """Stops clipping the form once it has finished expanding."""
        if self._form_expanded:
            self.form_container.clip_behavior = ft.ClipBehavior.NONE
            self.form_container.update()


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


def build_styled_data_table(
    columns: list[DataColumn2], rows: list[ft.DataRow], heading_color: str, **overrides: Any
) -> DataTable2:
    """Builds a `:class:DataTable2` styled consistently with every other table in the app.

    Args:
        columns (list[DataColumn2]): The columns of the table.
        rows (list[ft.DataRow]): The rows of the table.
        heading_color (str): The background color of the heading row.
        **overrides (Any): `DataTable2` keyword arguments replacing (or adding to) the shared styling.

    Returns:
        DataTable2: The styled table.
    """
    borders = ft.BorderSide(width=2)
    v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

    styling: dict[str, Any] = {
        "border": ft.Border(top=borders, bottom=borders, right=borders, left=borders),
        "vertical_lines": v_lines,
        "horizontal_lines": v_lines,
        "heading_text_style": ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
        "heading_row_color": heading_color,
        "sort_arrow_icon_color": ft.Colors.WHITE,
        "heading_row_height": 35,
        "horizontal_margin": 10,
        "column_spacing": 15,
    }
    styling.update(overrides)

    return DataTable2(columns=columns, rows=rows, **styling)  # type: ignore


def build_title_header(page: ft.Page) -> list[ft.Control]:
    """Builds the app-title block shared by the lock screen and the welcome page.

    Args:
        page (ft.Page): The page object. Its height must already be known.

    Returns:
        list[ft.Control]: The spacers and title texts, to be splatted into a column.
    """
    return [
        ft.Container(height=page.height * 0.1),  # type: ignore
        ft.Text("FINANCIAL TRACKER", size=30, weight=ft.FontWeight.BOLD),
        ft.Text("by Luca Marchetti", size=22),
        ft.Container(height=page.height * 0.2),  # type: ignore
    ]


def show_confirm_dialog(
    page: ft.Page, title: str, message: str, on_confirm: Callable[[ft.Event], None]
) -> None:
    """Shows a Yes/No confirmation dialog, where "No" just closes it.

    Args:
        page (ft.Page): The page object.
        title (str): The title of the dialog.
        message (str): The question to ask.
        on_confirm (Callable[[ft.Event], None]): The handler of the "Yes" button.
    """
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Yes", on_click=on_confirm),
                ft.TextButton("No", on_click=lambda _: page.pop_dialog()),
            ],
        )
    )


def build_row_action_button(
    icon: ft.IconData,
    row_id: int,
    on_click: ft.ControlEventHandler,
    color: str | None = None,
    disabled: bool = False,
    tooltip: str | None = None,
) -> ft.Button:
    """Builds an icon-only button for a table row's action cell, with the icon centered.

    The icon is passed as the button's `content` rather than its `icon`: an `icon` with no label is still laid out as
    icon + gap + empty label inside the default horizontal padding, which pushes it off-center in a 50px-wide button.

    Args:
        icon (ft.IconData): The icon to show.
        row_id (int): The id of the row the button acts on, stored as the button's `data`.
        on_click (ft.ControlEventHandler): The click handler.
        color (str | None): The icon color, or `None` for the theme default.
        disabled (bool): Whether the button is disabled.
        tooltip (str | None): The tooltip to show on hover.

    Returns:
        ft.Button: The action button.
    """
    return ft.Button(
        content=ft.Icon(icon),
        width=50,
        height=30,
        style=ft.ButtonStyle(padding=0),
        data=row_id,
        on_click=on_click,
        color=color,
        disabled=disabled,
        tooltip=tooltip,
    )


def show_alert(page: ft.Page, title: str, content: str) -> None:
    """Shows an error/info alert dialog with a "Dismiss" button.

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
