"""Implementation of the 'income' layout."""

from logging import getLogger

import flet as ft
from flet_datatable2 import DataColumn2

import database as db
from _helpers.constants import MONTHS
from _helpers.formatting import format_amount, parse_amount
from plotting import show_income_pie, show_income_summary

from .base_view import BaseCrudView
from .common import show_alert

logger = getLogger("financial_tracker")


class IncomeView(BaseCrudView):
    """Encapsulates the 'income' view logic and UI."""

    _heading_color = "#006400"
    _sorting_config_cls = db.IncomesSortingConfig

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
            options=[ft.DropdownOption(key=src, text=src) for src in db.fetch_sources()],
            on_text_change=lambda _: setattr(self.source_picker, "error_text", None),
            width=220,
        )

        # cost
        self.amount_text = ft.TextField(label="Amount (€)", width=150)

        # description
        self.description_text = ft.TextField(label="Description", width=570, multiline=True)

        # button
        self.add_income_button = ft.Button("Add Income", on_click=self.add_new_income)
        self.clear_button = self._build_clear_button()

        # data table
        columns = db.Income.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=200))
        columns[0].on_sort = self.sort_columns
        columns[3].on_sort = self.sort_columns

        columns[0].label.controls.append(self._build_month_filter_menu())  # type: ignore
        columns[2].label.controls.append(self._build_lookup_filter_menu(db.fetch_sources(), "Filter source"))  # type: ignore

        self.data_table = self._build_data_table(columns)
        self.table_column = ft.Column(controls=[self.data_table], expand=True, scroll=ft.ScrollMode.AUTO)

        # plotting
        self.summary_button = ft.Button(
            "Show Summary",
            icon=ft.Icons.BAR_CHART,
            color="#006400",
            on_click=lambda _: show_income_summary(self._page),
        )

        self.pie_chart_button = ft.Button(
            "Show Pie Chart",
            icon=ft.Icons.BAR_CHART,
            color="#000096",
            on_click=lambda _: show_income_pie(self._page, self.current_month_filter),
        )

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
            ft.Row([self.add_income_button, self.clear_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            self.table_column,
            ft.Row([self.summary_button, self.pie_chart_button], alignment=ft.MainAxisAlignment.CENTER),
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
            cost = parse_amount(self.amount_text.value)
        except ValueError:
            show_alert(self._page, "Invalid cost", "The cost must be a real number (comma for decimals allowed).")
            self._page.update()
            return None

        income = db.Income(
            month=int(self.month_picker.value),
            source=self.source_picker.value,
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

        db.add_item(self.location, income)
        self.clear_inputs()
        self.refresh_table()

    def delete_item(self, e: ft.Event) -> None:
        """Deletes an income from the database."""
        logger.info("Called 'delete_item'")
        income_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the income."""
            success = db.remove_item(self.location, db.WhichDb.INCOMES, income_id)
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

    def edit_this_item(self, e: ft.Event) -> None:
        """Edits an income."""
        logger.info("Called 'edit_this_item'")

        income_id = e.control.data
        old_income = db.fetch_by_id(self.location, db.WhichDb.INCOMES, income_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the income."""
            new_income = self.get_income_from_inputs()
            if new_income is None:
                return

            if new_income == old_income:
                show_alert(self._page, "Unchanged income", "You did not modify the income.")
                return

            success = db.edit_item(self.location, income_id, old_income, new_income)
            if not success:
                show_alert(self._page, "Error modifying income", f"It was not possible to modify income {income_id}")

            self.clear_inputs()
            self.reset_add_button()

            self.refresh_table()

        self.add_income_button.content = "Edit Income"
        self.add_income_button.color = ft.Colors.PURPLE
        self.add_income_button.on_click = modify

        self.fill_inputs_from_income(old_income)

    def copy_this_item(self, e: ft.Event) -> None:
        """Prefills the add-income form from an existing income, to add it as a new entry."""
        logger.info("Called 'copy_this_item'")
        income_id = e.control.data
        income = db.fetch_by_id(self.location, db.WhichDb.INCOMES, income_id)

        self.reset_add_button()

        self.fill_inputs_from_income(income)

    def fill_inputs_from_income(self, income: db.Income) -> None:
        """Populates the add-income controls with an existing income's values."""
        self.month_picker.value = str(income.month)
        self.source_picker.value = income.source
        self.amount_text.value = format_amount(income.amount)
        self.description_text.value = income.description

    def reset_add_button(self) -> None:
        """Resets the add button to its base "Add Income" state."""
        self.add_income_button.content = "Add Income"
        self.add_income_button.color = None
        self.add_income_button.on_click = self.add_new_income

    def _fetch_rows(self) -> db.RowGenerator:
        """Fetches incomes matching the current sort and filters."""
        self._profit_income_ids = db.fetch_profit_income_ids(self.location)
        return db.fetch_incomes(self.location, self.current_sort, self.current_month_filter, self.current_enum_filter)

    def _is_readonly(self, row_id: int) -> bool:
        """An income generated from a transfer's profit is only editable from the Transfers page."""
        return row_id in self._profit_income_ids


def income_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return IncomeView(page)
