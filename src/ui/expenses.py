"""Implementation of the 'add expense' layout."""

from datetime import datetime
from logging import getLogger
from sqlite3 import OperationalError

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from _helpers.constants import MONTHS
from plotting import show_expenses_pie, show_expenses_summary

logger = getLogger("financial_tracker")

DATE_OPTIONS = [
    ft.DropdownOption(key="day", text="Day"),
    ft.DropdownOption(key="range", text="Range"),
]

CATEGORIES = [
    ft.DropdownOption(
        key=str(cat.value),
        text=cat.name.lower().capitalize().replace("_", " "),
    )
    for cat in sorted(db.Categories, key=lambda c: c.name)
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


class ExpensesView(ft.Column):
    """Encapsulates the 'add expense' view logic and UI."""

    def __init__(self, page: ft.Page):
        """Initializes the view, state variables, and layout."""
        super().__init__()
        self._page = page

        if (year := self._page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")
        self.year = int(year)

        self.current_month_filter: int | None = None
        self.current_category_filter: db.Categories | None = None
        self.current_sort: db.ESC | None = None
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
            options=CATEGORIES,
            on_text_change=lambda _: setattr(self.category_picker, "error_text", None),
            width=220,
        )

        # cost
        self.cost_text = ft.TextField(label="Cost (€)", width=120)

        # description
        self.description_text = ft.TextField(label="Description", width=720, multiline=True)

        # button
        self.add_expense_button = ft.Button("Add Expense", on_click=self.add_new_expense)

        # data table
        columns = db.Expense.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=200))
        columns[0].on_sort = self.sort_columns
        columns[4].on_sort = self.sort_columns

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

        category_filter_menu = ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_color=ft.Colors.WHITE,
            icon_size=20,
            padding=0,
            menu_padding=0,
            tooltip="Filter category",
            items=[
                ft.PopupMenuItem(
                    cat.name.lower().capitalize().replace("_", " "), data=cat, on_click=self.filter_categories
                )
                for cat in sorted(db.Categories, key=lambda c: c.name)
            ]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=None, on_click=self.filter_categories)],
        )
        columns[3].label.controls.append(category_filter_menu)  # type: ignore

        borders = ft.BorderSide(width=2)
        v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

        self.data_table = DataTable2(
            fixed_top_rows=1,
            border=ft.Border(top=borders, bottom=borders, right=borders, left=borders),
            vertical_lines=v_lines,
            horizontal_lines=v_lines,
            heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
            heading_row_color="#960000",
            heading_row_height=35,
            horizontal_margin=0,
            column_spacing=15,
            columns=columns,  # type: ignore
            rows=[],
        )
        self.table_column = ft.Column(controls=[self.data_table])

        # plotting
        self.summary_button = ft.Button(
            "Show Summary",
            icon=ft.Icons.BAR_CHART,
            color="#006400",
            on_click=lambda _: show_expenses_summary(self._page),
        )

        self.pie_chart_button = ft.Button(
            "Show Pie Chart",
            icon=ft.Icons.BAR_CHART,
            color="#000096",
            on_click=lambda _: show_expenses_pie(self._page, self.current_month_filter),
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
            self.add_expense_button,
            ft.Container(height=10),
            self.table_column,
            ft.Row([self.summary_button, self.pie_chart_button], alignment=ft.MainAxisAlignment.CENTER),
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
            cost = float(self.cost_text.value.replace(",", "."))
        except ValueError:
            show_alert(self._page, "Invalid cost", "The cost must be a real number (comma for decimals allowed).")
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
            category=db.Categories(int(self.category_picker.value)),
            cost=cost,
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

        db.add_item(self.year, expense)
        self.clear_inputs()
        self.refresh_table()

    def delete_expense(self, e: ft.Event) -> None:
        """Deletes an expense from the database."""
        logger.info("Called 'delete_expense'")
        expense_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the expense."""
            success = db.remove_item(self.year, db.WhichDb.EXPENSES, expense_id)
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

    def edit_this_expense(self, e: ft.Event) -> None:
        """Edits an expense."""
        logger.info("Called 'edit_this_expense'")
        expense_id = e.control.data
        old_expense = db.fetch_by_id(self.year, db.WhichDb.EXPENSES, expense_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the expense."""
            new_expense = self.get_expense_from_inputs()
            if new_expense is None:
                return

            if new_expense == old_expense:
                show_alert(self._page, "Unchanged expense", "You did not modify the expense.")
                return

            success = db.edit_item(self.year, expense_id, old_expense, new_expense)
            if not success:
                show_alert(self._page, "Error modifying expense", f"It was not possible to modify expense {expense_id}")

            self.clear_inputs()
            self.add_expense_button.content = "Add Expense"
            self.add_expense_button.color = None
            self.add_expense_button.on_click = self.add_new_expense

            self.refresh_table()

        self.add_expense_button.content = "Edit Expense"
        self.add_expense_button.color = ft.Colors.PURPLE
        self.add_expense_button.on_click = modify

        self.fill_inputs_from_expense(old_expense, e)

    def copy_this_expense(self, e: ft.Event) -> None:
        """Prefills the add-expense form from an existing expense, to add it as a new entry."""
        logger.info("Called 'copy_this_expense'")
        expense_id = e.control.data
        expense = db.fetch_by_id(self.year, db.WhichDb.EXPENSES, expense_id)

        self.add_expense_button.content = "Add Expense"
        self.add_expense_button.color = None
        self.add_expense_button.on_click = self.add_new_expense

        self.fill_inputs_from_expense(expense, e)

    def fill_inputs_from_expense(self, expense: db.Expense, e: ft.Event) -> None:
        """Populates the add-expense controls with an existing expense's values."""
        self.category_picker.value = str(expense.category.value)
        self.cost_text.value = f"{expense.cost:.2f}"
        self.description_text.value = expense.description

        if expense.day_end is not None:
            self.date_options_dropdown.value = "range"
            self.range_picker.start_value = datetime(year=self.year, month=expense.month, day=expense.day_start)
            self.range_picker.end_value = datetime(year=self.year, month=expense.month, day=expense.day_end)
        else:
            self.date_picker.value = datetime(year=self.year, month=expense.month, day=expense.day_start)
            self.date_options_dropdown.value = "day"

        self.update_date_text(e)

    def refresh_table(self) -> None:
        """Refreshes the table that displays the database."""
        logger.info("Called 'refresh_table'")
        self.data_table.rows.clear()

        rows = db.fetch_expenses(self.year, self.current_sort, self.current_month_filter, self.current_category_filter)
        for row_id, row_data in rows:
            delete_btn = ft.Button(icon=ft.Icons.DELETE, width=50, height=30, data=row_id, on_click=self.delete_expense)
            edit_btn = ft.Button(
                icon=ft.Icons.EDIT,
                width=50,
                height=30,
                data=row_id,
                on_click=self.edit_this_expense,
                color=ft.Colors.BLUE,
            )
            copy_btn = ft.Button(
                icon=ft.Icons.COPY,
                width=50,
                height=30,
                data=row_id,
                on_click=self.copy_this_expense,
                color=ft.Colors.GREEN,
            )
            row_data.append(ft.DataCell(ft.Row(controls=[edit_btn, copy_btn, delete_btn])))
            self.data_table.rows.append(ft.DataRow(cells=row_data))

        row_count = len(self.data_table.rows)
        self.table_column.expand = row_count > 10
        self.data_table.expand = row_count > 10

        self._page.update()

    def sort_columns(self, e: ft.DataColumnSortEvent) -> None:
        """Sorts the columns of the table."""
        self.data_table.sort_column_index = e.column_index
        self.data_table.sort_ascending = e.ascending

        self.current_sort = db.ExpensesSortingConfig(e.column_index, e.ascending)
        self.refresh_table()

    def filter_months(self, e: ft.Event) -> None:
        """Filters the month column."""
        month = e.control.data
        if month > 0:
            self.current_month_filter = month
        else:
            self.current_month_filter = None

        self.refresh_table()

    def filter_categories(self, e: ft.Event) -> None:
        """Filters the category column."""
        self.current_category_filter = e.control.data
        self.refresh_table()


def expenses_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return ExpensesView(page)
