"""Shared base class for the CRUD views (Expenses/Income/Transfers)."""

from abc import ABC, abstractmethod
from datetime import datetime
from logging import getLogger
from sqlite3 import OperationalError
from typing import ClassVar

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from _helpers.constants import MONTHS
from _helpers.expression_parser import evaluate_expression

from .common import (CollapsibleFormMixin, build_row_action_button,
                     build_styled_data_table, current_db_location,
                     show_alert, sync_filter_menu)

logger = getLogger("financial_tracker")


class BaseCrudView(CollapsibleFormMixin, ft.Column, ABC):
    """Shared scaffolding for a domain's add/edit/delete/sort/filter table view."""

    _title: ClassVar[str]
    _heading_color: ClassVar[str]
    _sorting_config_cls: ClassVar[type[db.SortingConfig]]
    # Whether the table opens filtered to the current month instead of showing the whole year.
    _default_to_current_month: ClassVar[bool] = False

    def __init__(self, page: ft.Page) -> None:
        """Initializes the view, state variables, and layout."""
        super().__init__()
        self._page = page

        self.location = current_db_location(page)

        self.default_date = datetime.today()
        self.current_month_filter: int | None = self.default_date.month if self._default_to_current_month else None
        self.current_lookup_filter: str | None = None
        self.current_sort: db.SortingConfig | None = None

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self._init_controls()
        self._init_collapsible_form()

        self.controls = [ft.Text(self._title, size=30, weight=ft.FontWeight.BOLD), *self._build_layout()]

        try:
            self.refresh_table()
        except OperationalError:
            pass

    @abstractmethod
    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view, including `self.form_content`."""

    @abstractmethod
    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""

    @abstractmethod
    def _fetch_rows(self) -> db.RowGenerator:
        """Fetches the rows to display, applying the current sort and filters."""

    @abstractmethod
    def delete_item(self, e: ft.Event) -> None:
        """Deletes the row identified by `e.control.data`."""

    @abstractmethod
    def edit_this_item(self, e: ft.Event) -> None:
        """Edits the row identified by `e.control.data`."""

    @abstractmethod
    def copy_this_item(self, e: ft.Event) -> None:
        """Prefills the add form from the row identified by `e.control.data`."""

    @abstractmethod
    def clear_inputs(self) -> None:
        """Clears the add-item input controls."""

    def _parse_amount_field(self, raw: str, title: str, noun: str) -> float | None:
        """Evaluates an amount field's expression, alerting the user if it isn't valid.

        Args:
            raw (str): The text typed into the field.
            title (str): The title of the alert shown when `raw` is invalid.
            noun (str): The name of the field in the alert's message, e.g. "cost".

        Returns:
            float | None: The evaluated amount, or `None` if `raw` is invalid (already alerted).
        """
        try:
            return evaluate_expression(raw)
        except ValueError:
            show_alert(
                self._page,
                title,
                f"The {noun} must be a real number or arithmetic expression (comma for decimals allowed).",
            )
            return None

    def _parse_optional_positive_amount(self, raw: str, title: str, noun: str) -> tuple[float | None, str | None] | None:
        """Evaluates an optional amount field that must be greater than zero when filled in.

        Args:
            raw (str): The text typed into the field; blank means "not set".
            title (str): The title of the alert shown when `raw` is invalid.
            noun (str): The name of the field in the alert's message, e.g. "fee".

        Returns:
            tuple[float | None, str | None] | None: The `(amount, expression)` pair, `(None, None)` for a
                blank field, or `None` if `raw` is invalid (already alerted).
        """
        if not raw:
            return None, None

        amount = self._parse_amount_field(raw, title, noun)
        if amount is None:
            return None

        if amount <= 0:
            show_alert(self._page, title, f"The {noun} must be greater than zero.")
            return None

        return amount, raw

    def _build_data_table(self, columns: list[DataColumn2]) -> DataTable2:
        """Builds the `:class:DataTable2` shared by every subclass, styled with `_heading_color`."""
        return build_styled_data_table(columns, [], self._heading_color)

    def _build_month_filter_menu(self) -> ft.PopupMenuButton:
        """Builds the "Filter month" popup menu shared by every subclass."""
        self.month_filter_menu = ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_size=20,
            padding=0,
            menu_padding=0,
            items=[
                ft.PopupMenuItem(f"{MONTHS[i]} ({i + 1})", data=i + 1, on_click=self.filter_months) for i in range(12)
            ]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=-1, on_click=self.filter_months)],
        )
        self._sync_month_filter_menu()
        return self.month_filter_menu

    def _sync_month_filter_menu(self) -> None:
        """Re-styles the month filter menu to reflect the active filter."""
        month = self.current_month_filter
        label = None if month is None else MONTHS[month - 1]
        sync_filter_menu(self.month_filter_menu, label, ft.Colors.WHITE, "Filter month")

    def _build_lookup_filter_menu(self, options: list[str], tooltip: str) -> ft.PopupMenuButton:
        """Builds the domain-specific lookup-list filter popup menu shared by every subclass."""
        self._lookup_filter_tooltip = tooltip
        self.lookup_filter_menu = ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_size=20,
            padding=0,
            menu_padding=0,
            items=[ft.PopupMenuItem(option, data=option, on_click=self.filter_lookup) for option in sorted(options)]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=None, on_click=self.filter_lookup)],
        )
        self._sync_lookup_filter_menu()
        return self.lookup_filter_menu

    def _sync_lookup_filter_menu(self) -> None:
        """Re-styles the lookup-list filter menu to reflect the active filter."""
        sync_filter_menu(
            self.lookup_filter_menu, self.current_lookup_filter, ft.Colors.WHITE, self._lookup_filter_tooltip
        )

    def _is_readonly(self, row_id: int) -> bool:
        """Whether the row's edit/copy/delete buttons should be disabled. Overridable per domain."""
        return False

    def _build_action_buttons(self, row_id: int) -> list[ft.Control]:
        """Builds the edit/copy/delete button triplet shared by every subclass's rows."""
        disabled = self._is_readonly(row_id)
        tooltip = "Managed from the Transfers page" if disabled else None

        edit_btn = build_row_action_button(
            ft.Icons.EDIT,
            row_id,
            self.edit_this_item,
            color=None if disabled else ft.Colors.BLUE,
            disabled=disabled,
            tooltip=tooltip,
        )
        copy_btn = build_row_action_button(
            ft.Icons.COPY,
            row_id,
            self.copy_this_item,
            color=None if disabled else ft.Colors.GREEN,
            disabled=disabled,
            tooltip=tooltip,
        )
        delete_btn = build_row_action_button(
            ft.Icons.DELETE, row_id, self.delete_item, disabled=disabled, tooltip=tooltip
        )
        return [edit_btn, copy_btn, delete_btn]

    def refresh_table(self) -> None:
        """Refreshes the table that displays the database."""
        logger.info("Called 'refresh_table'")
        self.data_table.rows.clear()

        for row_id, row_data in self._fetch_rows():
            row_data.append(ft.DataCell(ft.Row(controls=self._build_action_buttons(row_id))))
            self.data_table.rows.append(ft.DataRow(cells=row_data))

        self._page.update()

    def sort_columns(self, e: ft.DataColumnSortEvent) -> None:
        """Sorts the columns of the table."""
        self.data_table.sort_column_index = e.column_index
        self.data_table.sort_ascending = e.ascending

        self.current_sort = self._sorting_config_cls(e.column_index, e.ascending)
        self.refresh_table()

    def filter_months(self, e: ft.Event) -> None:
        """Filters the month column."""
        month = e.control.data
        self.current_month_filter = month if month > 0 else None
        self._sync_month_filter_menu()
        self.refresh_table()

    def filter_lookup(self, e: ft.Event) -> None:
        """Filters the domain-specific lookup-list column (category, source, or kind)."""
        self.current_lookup_filter = e.control.data
        self._sync_lookup_filter_menu()
        self.refresh_table()
