"""Implementation of the 'add expense' layout."""

from datetime import datetime
from logging import getLogger
from sqlite3 import OperationalError

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

from database import Categories, Expense
from database.operations import (SortingConfig, add_expense, fetch_expenses,
                                 remove_expense)

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
    for cat in Categories
]


def show_alert(page: ft.Page, title: str, content: str) -> None:
    """Shows alert for missing data.

    Args:
        page (ft.Page): The page object.
        title (str): The title of the alert dialog.
        content (str): The content of the alert dialog.
    """
    page.show_dialog(
        ft.CupertinoAlertDialog(
            title=ft.Text(title),
            content=ft.Text(content),
            actions=[ft.CupertinoDialogAction("Dismiss", on_click=lambda _: page.pop_dialog())],
        )
    )
    page.update()


def expenses_view(page: ft.Page) -> ft.Control:
    """Implementation of the 'add expense' view."""
    logger.info("Called 'add_expense_view'")
    # ensure valid values
    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retireve the current year.")
    year = int(year)

    def handle_date_options(_: ft.Event) -> None:
        """Shows a date picker or a date range picker depending of the choice."""
        if date_options_dropdown.value == "range":
            page.show_dialog(range_picker)
        else:
            page.show_dialog(date_picker)

    def update_date_text(_: ft.Event) -> None:
        """Updates the button text when a user makes a selection."""
        if date_options_dropdown.value == "range":
            if range_picker.start_value and range_picker.end_value:
                start = range_picker.start_value.astimezone().strftime("%d")  # type: ignore
                end = range_picker.end_value.astimezone().strftime("%d/%m")  # type: ignore
                date_button.content = f"{start}-{end}"
        else:
            if date_picker.value:
                date_button.content = date_picker.value.astimezone().strftime("%d/%m")  # type: ignore
        page.update()

    def update_date_button(_: ft.Event) -> None:
        """Updates the text of the date button."""
        if date_options_dropdown.value == "range":
            date_button.content = "Select range"
        else:
            value = date_picker.value or default_date
            date_button.content = value.astimezone().strftime("%d/%m")  # type: ignore

    def add_new_expense(_: ft.Event) -> None:
        """Adds a new expense based on the user's inputs."""
        logger.info("Called 'add_new_expense'")

        if category_picker.value is None:
            category_picker.error_text = "You must chose a category"
            page.update()
            return

        if description_text.value == "":
            show_alert(page, "Empty description", "You must add a description to the expense")
            page.update()
            return

        if cost_text.value == "":
            show_alert(page, "Empty cost", "You must add a cost to the expense")
            page.update()
            return

        try:
            cost = float(cost_text.value.replace(",", "."))
        except ValueError:
            show_alert(page, "Invalid cost", "The cost must be a real number (comma for decimals allowed).")
            page.update()
            return

        # date range
        if date_options_dropdown.value == "range":
            if range_picker.start_value is None or range_picker.end_value is None:
                show_alert(page, "Empty date range", "You must select a range of dates")
                page.update()
                return

            # convert to local timezone
            start_local = range_picker.start_value.astimezone()  # type: ignore
            end_local = range_picker.end_value.astimezone()  # type: ignore

            if start_local.month != end_local.month:
                show_alert(page, "Invalid range", "The start and end date must be in the same month.")
                page.update()
                return

            month = start_local.month
            day_start = start_local.day
            day_end = end_local.day

        # single date
        else:
            if date_picker.value is None:
                show_alert(page, "Empty date", "You must select a date")
                page.update()
                return

            date_local = date_picker.value.astimezone()  # type: ignore

            month = date_local.month
            day_start = date_local.day
            day_end = None

        # add expense
        expense = Expense(
            month=month,
            day_start=day_start,
            day_end=day_end,
            description=description_text.value,
            category=Categories(int(category_picker.value)),
            cost=cost,
        )
        add_expense(year, expense)

        # clear data
        if date_options_dropdown.value == "range":
            range_picker.start_value = None
            range_picker.end_value = None
        else:
            date_picker.value = None

        category_picker.value = None
        description_text.value = ""
        cost_text.value = ""
        logger.debug("Cleared expense data")

        date_button.content = default_date.strftime("%d/%m")
        date_options_dropdown.value = "day"
        refresh_table()

    def delete_expense(e: ft.Event) -> None:
        """Deletes an expense from the database."""
        logger.info("Called 'delete_expense'")

        expense_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the expense."""
            remove_expense(year, expense_id)
            page.pop_dialog()
            refresh_table()

        page.show_dialog(
            ft.CupertinoAlertDialog(
                title=ft.Text("Delete expense"),
                content=ft.Text("Are you sure you want to delete this entry?"),
                actions=[
                    ft.CupertinoDialogAction("Yes", destructive=True, on_click=delete),
                    ft.CupertinoDialogAction("No", default=True, on_click=lambda _: page.pop_dialog()),
                ],
            )
        )

    # TODO
    def duplicate_expense(e: ft.Event) -> None: ...

    def refresh_table(sort: SortingConfig | None = None) -> None:
        """Refreshes the dable that displays the database."""
        logger.info("Called 'refresh_table'")

        data_table.rows.clear()

        rows = fetch_expenses(year, sort)
        for id, row in rows:
            delete_button = ft.Button(icon=ft.Icons.DELETE, width=50, height=30, data=id, on_click=delete_expense)
            duplicate_button = ft.Button(
                icon=ft.Icons.COPY, width=50, height=30, data=id, on_click=duplicate_expense, color=ft.Colors.BLUE
            )
            row.append(ft.DataCell(ft.Row(controls=[duplicate_button, delete_button])))
            data_table.rows.append(ft.DataRow(cells=row))

        page.update()

    # TODO
    def sort_columns(e: ft.DataColumnSortEvent) -> None:
        """Sorts the columns of the table."""
        data_table.sort_column_index = e.column_index
        data_table.sort_ascending = e.ascending

        sort = SortingConfig(e.column_index, e.ascending)
        refresh_table(sort)

    default_date = datetime.today()
    date_picker = ft.DatePicker(value=default_date, on_change=update_date_text)
    range_picker = ft.DateRangePicker(on_change=update_date_text)
    date_options_dropdown = ft.Dropdown(value="day", options=DATE_OPTIONS, width=120, on_text_change=update_date_button)
    date_button = ft.Button(
        content=default_date.strftime("%d/%m"),
        icon=ft.Icons.CALENDAR_MONTH,
        on_click=handle_date_options,
        width=170,
    )
    category_picker = ft.Dropdown(
        label="Category",
        options=CATEGORIES,
        on_text_change=lambda _: setattr(category_picker, "error_text", None),
        width=220,
    )

    columns = Expense.get_table_columns()
    columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=150))
    columns[0].on_sort = sort_columns  # month and day
    columns[4].on_sort = sort_columns  # cost
    data_table = DataTable2(
        fixed_top_rows=1,
        min_width=600,
        expand=True,
        heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
        heading_row_color=ft.Colors.LIGHT_BLUE,
        heading_row_height=35,
        columns=columns,  # type: ignore
        rows=[],
    )

    upper_row = ft.Row(
        controls=[
            date_options_dropdown,
            date_button,
            ft.Container(width=20),
            category_picker,
            ft.Container(width=20),
            cost_text := ft.TextField(label="Cost (€)", width=120),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    content = ft.Column(
        controls=[
            ft.Container(height=40),
            upper_row,
            description_text := ft.TextField(label="Description", width=720, multiline=True),
            ft.Button("Add Expense", on_click=add_new_expense),
            ft.Container(height=50),
            ft.Column(controls=[data_table], expand=True),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    try:
        refresh_table()
    except OperationalError:
        pass

    return content
