"""Implementation of the 'add expense' layout."""

from datetime import datetime
from logging import getLogger

import flet as ft
from flet_datatable2 import DataColumn2

import database as db
from _helpers.expression_parser import evaluate_expression
from _helpers.formatting import format_amount
from plotting import show_expenses_pie, show_expenses_summary, show_expenses_trend

from .base_view import BaseCrudView
from .common import show_alert

logger = getLogger("financial_tracker")

DATE_OPTIONS = [
    ft.DropdownOption(key="day", text="Day"),
    ft.DropdownOption(key="range", text="Range"),
]


class ExpensesView(BaseCrudView):
    """Encapsulates the 'add expense' view logic and UI."""

    _title = "Expenses"
    _heading_color = "#960000"
    _sorting_config_cls = db.ExpensesSortingConfig

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        # date
        self.date_picker = ft.DatePicker(value=self.default_date, on_change=self.update_date_text)
        self.range_picker = ft.DateRangePicker(on_change=self.update_date_text)
        self.date_options_dropdown = ft.Dropdown(
            value="day", options=DATE_OPTIONS, width=120, on_text_change=self.update_date_button
        )
        self.date_button = ft.Button(
            content=self.default_date.strftime("%d/%m"),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_date_options,
            width=170,
        )

        # category
        self.category_picker = ft.Dropdown(
            label="Category",
            options=[ft.DropdownOption(key=cat, text=cat) for cat in db.fetch_categories()],
            on_text_change=lambda _: setattr(self.category_picker, "error_text", None),
            width=220,
        )

        # cost
        self.cost_text = ft.TextField(label="Cost (€)", width=120)

        # description
        self.description_text = ft.TextField(label="Description", width=720, multiline=True)

        # button
        self.add_expense_button = ft.Button("Add Expense", on_click=self.add_new_expense)
        self.clear_button = self._build_clear_button()

        # data table
        columns = db.Expense.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=200))
        columns[0].on_sort = self.sort_columns
        columns[4].on_sort = self.sort_columns

        columns[0].label.controls.append(self._build_month_filter_menu())  # type: ignore
        columns[2].label.controls.append(self._build_lookup_filter_menu(db.fetch_categories(), "Filter category"))  # type: ignore

        self.data_table = self._build_data_table(columns)
        self.table_column = ft.Column(controls=[self.data_table], expand=True, scroll=ft.ScrollMode.AUTO)

        # plotting
        self.summary_button = ft.Button(
            "Show Summary",
            icon=ft.Icons.BAR_CHART,
            color="#006400",
            on_click=lambda _: show_expenses_summary(self._page, self.current_enum_filter),
        )

        self.pie_chart_button = ft.Button(
            "Show Pie Chart",
            icon=ft.Icons.BAR_CHART,
            color="#000096",
            on_click=lambda _: show_expenses_pie(self._page, self.current_month_filter),
        )

        self.trend_button = ft.Button(
            "Show Trend",
            icon=ft.Icons.BAR_CHART,
            color="#960000",
            on_click=lambda _: show_expenses_trend(self._page),
        )

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""
        upper_row = ft.Row(
            controls=[
                self.date_options_dropdown,
                self.date_button,
                ft.Container(width=20),
                self.category_picker,
                ft.Container(width=20),
                self.cost_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return [
            ft.Container(height=40),
            upper_row,
            self.description_text,
            ft.Row([self.add_expense_button, self.clear_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            self.table_column,
            ft.Row(
                [self.summary_button, self.pie_chart_button, self.trend_button], alignment=ft.MainAxisAlignment.CENTER
            ),
        ]

    def handle_date_options(self, _: ft.Event) -> None:
        """Shows a date picker or a date range picker depending on the choice."""
        if self.date_options_dropdown.value == "range":
            self._page.show_dialog(self.range_picker)
        else:
            self._page.show_dialog(self.date_picker)

    def update_date_text(self, _: ft.Event) -> None:
        """Updates the button text when a user makes a selection."""
        if self.date_options_dropdown.value == "range":
            if self.range_picker.start_value and self.range_picker.end_value:
                start = self.range_picker.start_value.astimezone().strftime("%d")  # type: ignore
                end = self.range_picker.end_value.astimezone().strftime("%d/%m")  # type: ignore
                self.date_button.content = f"{start}-{end}"
        else:
            if self.date_picker.value:
                self.date_button.content = self.date_picker.value.astimezone().strftime("%d/%m")  # type: ignore
        self._page.update()

    def update_date_button(self, _: ft.Event) -> None:
        """Updates the text of the date button when dropdown option changes."""
        if self.date_options_dropdown.value == "range":
            self.date_button.content = "Select range"
        else:
            value = self.date_picker.value or self.default_date
            self.date_button.content = value.astimezone().strftime("%d/%m")  # type: ignore
        self._page.update()

    def get_expense_from_inputs(self) -> db.Expense | None:
        """Reads the values in the controls and returns an :class:`Expense` object."""
        logger.info("Called 'get_expense_from_inputs'")

        if self.category_picker.value is None:
            self.category_picker.error_text = "You must choose a category"
            self._page.update()
            return None

        if self.description_text.value == "":
            show_alert(self._page, "Empty description", "You must add a description to the expense")
            self._page.update()
            return None

        if self.cost_text.value == "":
            show_alert(self._page, "Empty cost", "You must add a cost to the expense")
            self._page.update()
            return None

        try:
            cost = evaluate_expression(self.cost_text.value)
        except ValueError:
            show_alert(
                self._page,
                "Invalid cost",
                "The cost must be a real number or arithmetic expression (comma for decimals allowed).",
            )
            self._page.update()
            return None

        if self.date_options_dropdown.value == "range":
            if self.range_picker.start_value is None or self.range_picker.end_value is None:
                show_alert(self._page, "Empty date range", "You must select a range of dates")
                self._page.update()
                return None

            start_local = self.range_picker.start_value.astimezone()  # type: ignore
            end_local = self.range_picker.end_value.astimezone()  # type: ignore

            if start_local.month != end_local.month:
                show_alert(self._page, "Invalid range", "The start and end date must be in the same month.")
                self._page.update()
                return None

            month = start_local.month
            day_start = start_local.day
            day_end = end_local.day

        else:
            if self.date_picker.value is None:
                show_alert(self._page, "Empty date", "You must select a date")
                self._page.update()
                return None

            date_local = self.date_picker.value.astimezone()  # type: ignore

            month = date_local.month
            day_start = date_local.day
            day_end = None

        expense = db.Expense(
            month=month,
            day_start=day_start,
            day_end=day_end,
            description=self.description_text.value,
            category=self.category_picker.value,
            cost=cost,
            cost_expression=self.cost_text.value,
        )
        logger.debug(f"Reconstructed expense:\n{expense}")

        return expense

    def clear_inputs(self) -> None:
        """Clears the add expense controls."""
        logger.info("Called 'clear_inputs'")

        if self.date_options_dropdown.value == "range":
            self.range_picker.start_value = None
            self.range_picker.end_value = None
        else:
            self.date_picker.value = None

        self.category_picker.value = None
        self.description_text.value = ""
        self.cost_text.value = ""
        logger.debug("Cleared expense data")

        self.date_options_dropdown.value = "day"
        self.date_picker.value = self.default_date
        self.date_button.content = self.default_date.strftime("%d/%m")

    def add_new_expense(self, _: ft.Event) -> None:
        """Adds a new expense based on the user's inputs."""
        logger.info("Called 'add_new_expense'")

        expense = self.get_expense_from_inputs()
        if expense is None:
            return

        db.add_item(self.location, expense)
        self.clear_inputs()
        self.refresh_table()

    def delete_item(self, e: ft.Event) -> None:
        """Deletes an expense from the database."""
        logger.info("Called 'delete_item'")
        expense_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the expense."""
            success = db.remove_item(self.location, db.WhichDb.EXPENSES, expense_id)
            if not success:
                show_alert(self._page, "Error deleting expense", f"It was not possible to delete expense {expense_id}")

            self._page.pop_dialog()
            self.refresh_table()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete expense"),
                content=ft.Text("Are you sure you want to delete this expense?"),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def edit_this_item(self, e: ft.Event) -> None:
        """Edits an expense."""
        logger.info("Called 'edit_this_item'")
        expense_id = e.control.data
        old_expense = db.fetch_by_id(self.location, db.WhichDb.EXPENSES, expense_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the expense."""
            new_expense = self.get_expense_from_inputs()
            if new_expense is None:
                return

            if new_expense == old_expense:
                show_alert(self._page, "Unchanged expense", "You did not modify the expense.")
                return

            success = db.edit_item(self.location, expense_id, old_expense, new_expense)
            if not success:
                show_alert(self._page, "Error modifying expense", f"It was not possible to modify expense {expense_id}")

            self.clear_inputs()
            self.reset_add_button()

            self.refresh_table()

        self.add_expense_button.content = "Edit Expense"
        self.add_expense_button.color = ft.Colors.PURPLE
        self.add_expense_button.on_click = modify

        self.fill_inputs_from_expense(old_expense, e)

    def copy_this_item(self, e: ft.Event) -> None:
        """Prefills the add-expense form from an existing expense, to add it as a new entry."""
        logger.info("Called 'copy_this_item'")
        expense_id = e.control.data
        expense = db.fetch_by_id(self.location, db.WhichDb.EXPENSES, expense_id)

        self.reset_add_button()

        self.fill_inputs_from_expense(expense, e)

    def reset_add_button(self) -> None:
        """Resets the add button to its base "Add Expense" state."""
        self.add_expense_button.content = "Add Expense"
        self.add_expense_button.color = None
        self.add_expense_button.on_click = self.add_new_expense

    def fill_inputs_from_expense(self, expense: db.Expense, e: ft.Event) -> None:
        """Populates the add-expense controls with an existing expense's values."""
        self.category_picker.value = expense.category
        self.cost_text.value = (
            expense.cost_expression if expense.cost_expression is not None else format_amount(expense.cost)
        )
        self.description_text.value = expense.description

        if expense.day_end is not None:
            self.date_options_dropdown.value = "range"
            self.range_picker.start_value = datetime(year=self.year, month=expense.month, day=expense.day_start)
            self.range_picker.end_value = datetime(year=self.year, month=expense.month, day=expense.day_end)
        else:
            self.date_picker.value = datetime(year=self.year, month=expense.month, day=expense.day_start)
            self.date_options_dropdown.value = "day"

        self.update_date_text(e)

    def _fetch_rows(self) -> db.RowGenerator:
        """Fetches expenses matching the current sort and filters."""
        self._fee_expense_ids = db.fetch_fee_expense_ids(self.location)
        return db.fetch_expenses(self.location, self.current_sort, self.current_month_filter, self.current_enum_filter)

    def _is_readonly(self, row_id: int) -> bool:
        """An expense generated from a transfer's fee is only editable from the Transfers page."""
        return row_id in self._fee_expense_ids


def expenses_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return ExpensesView(page)
