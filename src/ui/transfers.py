"""Implementation of the 'transfers' layout."""

from datetime import datetime
from logging import getLogger
from sqlite3 import OperationalError

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from _helpers.constants import MONTHS

logger = getLogger("financial_tracker")

KINDS = [
    ft.DropdownOption(
        key=str(kind.value),
        text=kind.name.lower().capitalize().replace("_", " "),
    )
    for kind in sorted(db.Kind, key=lambda k: k.name)
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


class TransfersView(ft.Column):
    """Encapsulates the 'transfers' view logic and UI."""

    def __init__(self, page: ft.Page):
        """Initializes the view, state variables, and layout."""
        super().__init__()
        self._page = page

        if (year := self._page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")
        self.year = int(year)

        self.current_month_filter: int | None = None
        self.current_sort: db.TSC | None = None
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

        # kind
        self.kind_picker = ft.Dropdown(
            label="Kind",
            options=KINDS,
            on_text_change=lambda _: setattr(self.kind_picker, "error_text", None),
            width=220,
        )

        # amount
        self.amount_text = ft.TextField(label="Amount (€)", width=150)

        # source / destination
        self.source_text = ft.TextField(label="Source", width=266)
        self.destination_text = ft.TextField(label="Destination", width=266)

        # description
        self.description_text = ft.TextField(label="Description", width=572, multiline=True)

        # button
        self.add_transfer_button = ft.Button("Add Transfer", on_click=self.add_new_transfer)

        # data table
        columns = db.Transfer.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=150))
        columns[0].on_sort = self.sort_columns
        columns[5].on_sort = self.sort_columns

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
            heading_row_color="#00008B",
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
                self.kind_picker,
                ft.Container(width=20),
                self.amount_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        source_destination_row = ft.Row(
            controls=[
                self.source_text,
                ft.Container(width=20),
                self.destination_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return [
            ft.Container(height=40),
            upper_row,
            source_destination_row,
            self.description_text,
            self.add_transfer_button,
            ft.Container(height=10),
            self.table_column,
        ]

    def get_transfer_from_inputs(self) -> db.Transfer | None:
        """Reads the values in the controls and returns a `:class:Transfer` object."""
        logger.info("Called 'get_transfer_from_inputs'")

        if self.month_picker.value is None:
            show_alert(self._page, "Invalid month", "The month cannot be empty.")
            self._page.update()
            return None

        if self.description_text.value == "":
            show_alert(self._page, "Empty description", "You must add a description to the transfer")
            self._page.update()
            return None

        if self.kind_picker.value is None:
            self.kind_picker.error_text = "You must choose a kind"
            self._page.update()
            return None

        if self.amount_text.value == "":
            show_alert(self._page, "Empty amount", "You must add an amount to the transfer")
            self._page.update()
            return None

        try:
            amount = float(self.amount_text.value.replace(",", "."))
        except ValueError:
            show_alert(self._page, "Invalid amount", "The amount must be a real number (comma for decimals allowed).")
            self._page.update()
            return None

        source = self.source_text.value or None
        destination = self.destination_text.value or None
        if source is None and destination is None:
            show_alert(
                self._page,
                "Missing source/destination",
                "A transfer must have a source or a destination.",
            )
            self._page.update()
            return None

        transfer = db.Transfer(
            month=int(self.month_picker.value),
            kind=db.Kind(int(self.kind_picker.value)),
            description=self.description_text.value,
            source=source,
            destination=destination,
            amount=amount,
        )
        logger.debug(f"Reconstructed transfer:\n{transfer}")

        return transfer

    def clear_inputs(self) -> None:
        """Clears the add transfer controls."""
        logger.info("Called 'clear_inputs'")

        self.month_picker.value = str(self.default_date.month)
        self.description_text.value = ""
        self.kind_picker.value = None
        self.amount_text.value = ""
        self.source_text.value = ""
        self.destination_text.value = ""
        logger.debug("Cleared transfer data")

    def add_new_transfer(self, _: ft.Event) -> None:
        """Adds a new transfer based on the user's inputs."""
        logger.info("Called 'add_new_transfer'")

        transfer = self.get_transfer_from_inputs()
        if transfer is None:
            return

        db.add_item(self.year, transfer)
        self.clear_inputs()
        self.refresh_table()

    def delete_transfer(self, e: ft.Event) -> None:
        """Deletes a transfer from the database."""
        logger.info("Called 'delete_transfer'")
        transfer_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the transfer."""
            success = db.remove_item(self.year, db.WhichDb.TRANSFERS, transfer_id)
            if not success:
                show_alert(
                    self._page, "Error deleting transfer", f"It was not possible to delete transfer {transfer_id}"
                )

            self._page.pop_dialog()
            self.refresh_table()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete transfer"),
                content=ft.Text("Are you sure you want to delete this transfer?"),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def edit_this_transfer(self, e: ft.Event) -> None:
        """Edits a transfer."""
        logger.info("Called 'edit_this_transfer'")

        transfer_id = e.control.data
        old_transfer = db.fetch_by_id(self.year, db.WhichDb.TRANSFERS, transfer_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the transfer."""
            new_transfer = self.get_transfer_from_inputs()
            if new_transfer is None:
                return

            if new_transfer == old_transfer:
                show_alert(self._page, "Unchanged transfer", "You did not modify the transfer.")
                return

            success = db.edit_item(self.year, transfer_id, old_transfer, new_transfer)
            if not success:
                show_alert(
                    self._page, "Error modifying transfer", f"It was not possible to modify transfer {transfer_id}"
                )

            self.clear_inputs()
            self.add_transfer_button.content = "Add Transfer"
            self.add_transfer_button.color = None
            self.add_transfer_button.on_click = self.add_new_transfer

            self.refresh_table()

        self.add_transfer_button.content = "Edit Transfer"
        self.add_transfer_button.color = ft.Colors.PURPLE
        self.add_transfer_button.on_click = modify

        self.month_picker.value = str(old_transfer.month)
        self.kind_picker.value = str(old_transfer.kind.value)
        self.amount_text.value = f"{old_transfer.amount:.2f}"
        self.description_text.value = old_transfer.description
        self.source_text.value = old_transfer.source or ""
        self.destination_text.value = old_transfer.destination or ""

    def refresh_table(self) -> None:
        """Refreshes the table that displays the database."""
        logger.info("Called 'refresh_table'")
        self.data_table.rows.clear()

        rows = db.fetch_transfers(self.year, self.current_sort, self.current_month_filter)
        for row_id, row_data in rows:
            delete_btn = ft.Button(
                icon=ft.Icons.DELETE,
                width=50,
                height=30,
                data=row_id,
                on_click=self.delete_transfer,
            )
            edit_btn = ft.Button(
                icon=ft.Icons.EDIT,
                width=50,
                height=30,
                data=row_id,
                on_click=self.edit_this_transfer,
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

        self.current_sort = db.TransfersSortingConfig(e.column_index, e.ascending)
        self.refresh_table()

    def filter_months(self, e: ft.Event) -> None:
        """Filters the month column."""
        month = e.control.data
        if month > 0:
            self.current_month_filter = month
        else:
            self.current_month_filter = None

        self.refresh_table()


def transfers_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return TransfersView(page)
