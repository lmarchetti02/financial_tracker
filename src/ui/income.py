"""Implementation of the 'income' layout."""

from datetime import datetime
from logging import getLogger
from sqlite3 import OperationalError

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from helpers.constants import MONTHS

logger = getLogger("financial_tracker")

SOURCES = [
    ft.DropdownOption(
        key=str(src.value),
        text=src.name.lower().capitalize().replace("_", " "),
    )
    for src in sorted(db.Sources, key=lambda s: s.name)
]


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


class IncomeView(ft.Column):
    """Encapsulates the 'income' view logic and UI."""

    def __init__(self, page: ft.Page):
        """Initializes the view, state variables, and layout."""
        super().__init__()
        self._page = page

        if (year := self._page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")
        self.year = int(year)

        self.current_month_filter: int | None = None
        self.current_sort: db.ISC | None = None
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

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        # month
        self.month_picker = ft.Dropdown(
            label="Month",
            value=str(self.default_date.month),
            options=[ft.DropdownOption(key=str(i + 1), text=m) for i, m in enumerate(MONTHS)],
        )

        # source
        self.source_picker = ft.Dropdown(
            label="Source",
            options=SOURCES,
            on_text_change=lambda _: setattr(self.source_picker, "error_text", None),
            width=220,
        )

        # cost
        self.amount_text = ft.TextField(label="Amount (€)", width=150)

        # description
        self.description_text = ft.TextField(label="Description", width=570, multiline=True)

        # button
        self.add_income_button = ft.Button("Add Income", on_click=self.add_new_income)

        # data table
        columns = db.Income.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=150))
        columns[0].on_sort = self.sort_columns
        columns[2].on_sort = self.sort_columns

        filter_menu = ft.PopupMenuButton(
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
        columns[0].label.controls.append(filter_menu)  # type: ignore

        borders = ft.BorderSide(width=2)
        v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

        self.data_table = DataTable2(
            fixed_top_rows=1,
            border=ft.Border(top=borders, bottom=borders, right=borders, left=borders),
            vertical_lines=v_lines,
            horizontal_lines=v_lines,
            heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
            heading_row_color="#006400",
            heading_row_height=35,
            horizontal_margin=0,
            column_spacing=15,
            columns=columns,  # type: ignore
            rows=[],
        )
        self.table_column = ft.Column(controls=[self.data_table])

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""
        upper_row = ft.Row(
            controls=[
                self.month_picker,
                ft.Container(width=20),
                self.source_picker,
                ft.Container(width=20),
                self.amount_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return [
            ft.Container(height=40),
            upper_row,
            self.description_text,
            self.add_income_button,
            ft.Container(height=10),
            self.table_column,
        ]

    def get_income_from_inputs(self) -> db.Income | None:
        """Reads the values in the controls and returns an :class:`Income` object."""
        logger.info("Called 'get_income_from_inputs'")

        if self.month_picker.value is None:
            show_alert(self._page, "Invalid month", "The month cannot be empty.")
            self._page.update()
            return None

        if self.description_text.value == "":
            show_alert(self._page, "Empty description", "You must add a description to the income")
            self._page.update()
            return None

        if self.source_picker.value is None:
            self.source_picker.error_text = "You must choose a source"
            self._page.update()
            return None

        if self.amount_text.value == "":
            show_alert(self._page, "Empty cost", "You must add a cost to the expense")
            self._page.update()
            return None

        try:
            cost = float(self.amount_text.value.replace(",", "."))
        except ValueError:
            show_alert(self._page, "Invalid cost", "The cost must be a real number (comma for decimals allowed).")
            self._page.update()
            return None

        income = db.Income(
            month=int(self.month_picker.value),
            source=db.Sources(int(self.source_picker.value)),
            description=self.description_text.value,
            amount=cost,
        )
        logger.debug(f"Reconstructed income:\n{income}")

        return income

    def clear_inputs(self) -> None:
        """Clears the add income controls."""
        logger.info("Called 'clear_inputs'")

        self.month_picker.value = str(self.default_date.month)
        self.description_text.value = ""
        self.source_picker.value = None
        self.amount_text.value = ""
        logger.debug("Cleared expense data")

    def add_new_income(self, _: ft.Event) -> None:
        """Adds a new income based on the user's inputs."""
        logger.info("Called 'add_new_income'")

        income = self.get_income_from_inputs()
        if income is None:
            return

        db.add_item(self.year, income)
        self.clear_inputs()
        self.refresh_table()

    def delete_income(self, e: ft.Event) -> None:
        """Deletes an income from the database."""
        logger.info("Called 'delete_income'")
        income_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the income."""
            success = db.remove_item(self.year, db.WhichDb.INCOMES, income_id)
            if not success:
                show_alert(self._page, "Error deleting income", f"It was not possible to delete income {income_id}")

            self._page.pop_dialog()
            self.refresh_table()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete income"),
                content=ft.Text("Are you sure you want to delete this income?"),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def edit_this_income(self, e: ft.Event) -> None:
        """Edits an income."""
        logger.info("Called 'edit_this_income'")

        income_id = e.control.data
        old_income = db.fetch_by_id(self.year, db.WhichDb.INCOMES, income_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the income."""
            new_income = self.get_income_from_inputs()
            if new_income is None:
                return

            if new_income == old_income:
                show_alert(self._page, "Unchanged income", "You did not modify the income.")
                return

            success = db.edit_item(self.year, income_id, old_income, new_income)
            if not success:
                show_alert(self._page, "Error modifying income", f"It was not possible to modify income {income_id}")

            self.clear_inputs()
            self.add_income_button.content = "Add Income"
            self.add_income_button.color = None
            self.add_income_button.on_click = self.add_new_income

            self.refresh_table()

        self.add_income_button.content = "Edit Income"
        self.add_income_button.color = ft.Colors.PURPLE
        self.add_income_button.on_click = modify

        self.month_picker.value = str(old_income.month)
        self.source_picker.value = str(old_income.source.value)
        self.amount_text.value = f"{old_income.amount:.2f}"
        self.description_text.value = old_income.description

    def refresh_table(self) -> None:
        """Refreshes the table that displays the database."""
        logger.info("Called 'refresh_table'")
        self.data_table.rows.clear()

        rows = db.fetch_incomes(self.year, self.current_sort, self.current_month_filter)
        for row_id, row_data in rows:
            delete_btn = ft.Button(
                icon=ft.Icons.DELETE,
                width=50,
                height=30,
                data=row_id,
                on_click=self.delete_income,
            )
            edit_btn = ft.Button(
                icon=ft.Icons.EDIT,
                width=50,
                height=30,
                data=row_id,
                on_click=self.edit_this_income,
                color=ft.Colors.BLUE,
            )
            row_data.append(ft.DataCell(ft.Row(controls=[edit_btn, delete_btn])))
            self.data_table.rows.append(ft.DataRow(cells=row_data))

        row_count = len(self.data_table.rows)
        self.table_column.expand = row_count > 10
        self.data_table.expand = row_count > 10

        self._page.update()

    def sort_columns(self, e: ft.DataColumnSortEvent) -> None:
        """Sorts the columns of the table."""
        self.data_table.sort_column_index = e.column_index
        self.data_table.sort_ascending = e.ascending

        self.current_sort = db.IncomesSortingConfig(e.column_index, e.ascending)
        self.refresh_table()

    def filter_months(self, e: ft.Event) -> None:
        """Filters the month column."""
        month = e.control.data
        if month > 0:
            self.current_month_filter = month
        else:
            self.current_month_filter = None

        self.refresh_table()


def income_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return IncomeView(page)
