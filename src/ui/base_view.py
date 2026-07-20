"""Shared base class for the CRUD views (Expenses/Income/Transfers)."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from logging import getLogger
from sqlite3 import OperationalError
from typing import ClassVar

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from _helpers.constants import MONTHS
from _helpers.formatting import enum_label

logger = getLogger("financial_tracker")


class BaseCrudView(ft.Column, ABC):
    """Shared scaffolding for a domain's add/edit/delete/sort/filter table view."""

    _heading_color: ClassVar[str]
    _sorting_config_cls: ClassVar[type[db.SortingConfig]]

    def __init__(self, page: ft.Page) -> None:
        """Initializes the view, state variables, and layout."""
        super().__init__()
        self._page = page

        if (year := self._page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")
        self.year = int(year)

        self.current_month_filter: int | None = None
        self.current_enum_filter: Enum | None = None
        self.current_sort: db.SortingConfig | None = None
        self.default_date = datetime.today()

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self._init_controls()
        self.controls = self._build_layout()

        try:
            self.refresh_table()
        except OperationalError:
            pass

    @abstractmethod
    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""

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

    @abstractmethod
    def reset_add_button(self) -> None:
        """Resets the add button to its base "Add ..." label, color, and click handler."""

    def _handle_clear_click(self, _: ft.Event) -> None:
        """Clears the add-item inputs, resets the add button, and pushes the change to the page."""
        self.clear_inputs()
        self.reset_add_button()
        self._page.update()

    def _build_clear_button(self) -> ft.Button:
        """Builds the "Clear Fields" button shared by every subclass."""
        return ft.Button("Clear Fields", on_click=self._handle_clear_click)

    def _build_data_table(self, columns: list[DataColumn2]) -> DataTable2:
        """Builds the `:class:DataTable2` shared by every subclass, styled with `_heading_color`."""
        borders = ft.BorderSide(width=2)
        v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

        return DataTable2(
            fixed_top_rows=1,
            border=ft.Border(top=borders, bottom=borders, right=borders, left=borders),
            vertical_lines=v_lines,
            horizontal_lines=v_lines,
            heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
            heading_row_color=self._heading_color,
            sort_arrow_icon_color=ft.Colors.WHITE,
            heading_row_height=35,
            horizontal_margin=0,
            column_spacing=15,
            columns=columns,  # type: ignore
            rows=[],
        )

    def _build_month_filter_menu(self) -> ft.PopupMenuButton:
        """Builds the "Filter month" popup menu shared by every subclass."""
        return ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_color=ft.Colors.WHITE,
            icon_size=20,
            padding=0,
            menu_padding=0,
            tooltip="Filter month",
            items=[
                ft.PopupMenuItem(f"{MONTHS[i]} ({i + 1})", data=i + 1, on_click=self.filter_months) for i in range(12)
            ]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=-1, on_click=self.filter_months)],
        )

    def _build_enum_filter_menu(self, enum_cls: type[Enum], tooltip: str) -> ft.PopupMenuButton:
        """Builds the domain-enum filter popup menu shared by every subclass."""
        return ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_color=ft.Colors.WHITE,
            icon_size=20,
            padding=0,
            menu_padding=0,
            tooltip=tooltip,
            items=[
                ft.PopupMenuItem(enum_label(member), data=member, on_click=self.filter_enum)
                for member in sorted(enum_cls, key=lambda m: m.name)
            ]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=None, on_click=self.filter_enum)],
        )

    def _is_readonly(self, row_id: int) -> bool:
        """Whether the row's edit/copy/delete buttons should be disabled. Overridable per domain."""
        return False

    def _build_action_buttons(self, row_id: int) -> list[ft.Control]:
        """Builds the edit/copy/delete button triplet shared by every subclass's rows."""
        disabled = self._is_readonly(row_id)
        tooltip = "Managed from the Transfers page" if disabled else None

        edit_btn = ft.Button(
            icon=ft.Icons.EDIT,
            width=50,
            height=30,
            data=row_id,
            on_click=self.edit_this_item,
            color=None if disabled else ft.Colors.BLUE,
            disabled=disabled,
            tooltip=tooltip,
        )
        copy_btn = ft.Button(
            icon=ft.Icons.COPY,
            width=50,
            height=30,
            data=row_id,
            on_click=self.copy_this_item,
            color=None if disabled else ft.Colors.GREEN,
            disabled=disabled,
            tooltip=tooltip,
        )
        delete_btn = ft.Button(
            icon=ft.Icons.DELETE,
            width=50,
            height=30,
            data=row_id,
            on_click=self.delete_item,
            disabled=disabled,
            tooltip=tooltip,
        )
        return [edit_btn, copy_btn, delete_btn]

    def refresh_table(self) -> None:
        """Refreshes the table that displays the database."""
        logger.info("Called 'refresh_table'")
        self.data_table.rows.clear()

        for row_id, row_data in self._fetch_rows():
            row_data.append(ft.DataCell(ft.Row(controls=self._build_action_buttons(row_id))))
            self.data_table.rows.append(ft.DataRow(cells=row_data))

        row_count = len(self.data_table.rows)
        self.table_column.expand = row_count > 10
        self.data_table.expand = row_count > 10

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
        self.refresh_table()

    def filter_enum(self, e: ft.Event) -> None:
        """Filters the domain-specific enum column."""
        self.current_enum_filter = e.control.data
        self.refresh_table()
