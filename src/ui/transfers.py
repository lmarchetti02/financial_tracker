"""Implementation of the 'transfers' layout."""

from dataclasses import replace
from datetime import datetime
from logging import getLogger

import flet as ft
from flet_datatable2 import DataColumn2

import database as db
from _helpers.formatting import enum_label

from .base_view import BaseCrudView
from .common import show_alert

logger = getLogger("financial_tracker")

KINDS = [
    ft.DropdownOption(
        key=str(kind.value),
        text=enum_label(kind),
    )
    for kind in sorted(db.Kind, key=lambda k: k.name)
]


class TransfersView(BaseCrudView):
    """Encapsulates the 'transfers' view logic and UI."""

    _heading_color = "#00008B"
    _sorting_config_cls = db.TransfersSortingConfig

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        # date
        self.date_picker = ft.DatePicker(value=self.default_date, on_change=self.update_date_text)
        self.date_button = ft.Button(
            content=self.default_date.strftime("%d/%m"),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_date_picker,
            width=150,
        )

        # kind
        self.kind_picker = ft.Dropdown(
            label="Kind",
            options=KINDS,
            on_text_change=lambda _: setattr(self.kind_picker, "error_text", None),
            width=180,
        )

        # amount
        self.amount_text = ft.TextField(label="Amount (€)", width=150)

        # source / destination
        self.source_text = ft.TextField(label="Source", width=260)
        self.destination_text = ft.TextField(label="Destination", width=260)

        # description
        self.description_text = ft.TextField(label="Description", width=400, multiline=True)

        # fee
        self.fee_text = ft.TextField(label="Fee (€)", width=120)

        # button
        self.add_transfer_button = ft.Button("Add Transfer", on_click=self.add_new_transfer)

        # data table
        columns = db.Transfer.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=200))
        columns[0].on_sort = self.sort_columns
        columns[6].on_sort = self.sort_columns

        columns[0].label.controls.append(self._build_month_filter_menu())  # type: ignore
        columns[2].label.controls.append(self._build_enum_filter_menu(db.Kind, "Filter kind"))  # type: ignore

        self.data_table = self._build_data_table(columns)
        self.table_column = ft.Column(controls=[self.data_table])

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""
        upper_row = ft.Row(
            controls=[
                self.date_button,
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

        description_row = ft.Row(
            controls=[
                self.description_text,
                ft.Container(width=20),
                self.fee_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return [
            ft.Container(height=40),
            upper_row,
            source_destination_row,
            description_row,
            self.add_transfer_button,
            ft.Container(height=10),
            self.table_column,
        ]

    def handle_date_picker(self, _: ft.Event) -> None:
        """Shows the date picker."""
        self._page.show_dialog(self.date_picker)

    def update_date_text(self, _: ft.Event) -> None:
        """Updates the button text when a user picks a date."""
        if self.date_picker.value:
            self.date_button.content = self.date_picker.value.astimezone().strftime("%d/%m")
        self._page.update()

    def get_transfer_from_inputs(self) -> db.Transfer | None:
        """Reads the values in the controls and returns a `:class:Transfer` object."""
        logger.info("Called 'get_transfer_from_inputs'")

        if self.date_picker.value is None:
            show_alert(self._page, "Empty date", "You must select a date")
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

        fee = None
        if self.fee_text.value:
            try:
                fee = float(self.fee_text.value.replace(",", "."))
            except ValueError:
                show_alert(self._page, "Invalid fee", "The fee must be a real number (comma for decimals allowed).")
                self._page.update()
                return None

            if fee <= 0:
                show_alert(self._page, "Invalid fee", "The fee must be greater than zero.")
                self._page.update()
                return None

        date_local = self.date_picker.value.astimezone()

        transfer = db.Transfer(
            month=date_local.month,
            day=date_local.day,
            kind=db.Kind(int(self.kind_picker.value)),
            description=self.description_text.value,
            source=source,
            destination=destination,
            amount=amount,
            fee=fee,
        )
        logger.debug(f"Reconstructed transfer:\n{transfer}")

        return transfer

    def clear_inputs(self) -> None:
        """Clears the add transfer controls."""
        logger.info("Called 'clear_inputs'")

        self.date_picker.value = self.default_date
        self.date_button.content = self.default_date.strftime("%d/%m")
        self.description_text.value = ""
        self.kind_picker.value = None
        self.amount_text.value = ""
        self.fee_text.value = ""
        self.source_text.value = ""
        self.destination_text.value = ""
        logger.debug("Cleared transfer data")

    def add_new_transfer(self, _: ft.Event) -> None:
        """Adds a new transfer based on the user's inputs."""
        logger.info("Called 'add_new_transfer'")

        transfer = self.get_transfer_from_inputs()
        if transfer is None:
            return

        transfer_id = db.add_item(self.year, transfer)

        if transfer.fee is not None:
            fee_expense = db.Expense(
                month=transfer.month,
                day_start=transfer.day,
                description=transfer.description,
                category=db.Categories.TRADING_FEE,
                cost=transfer.fee,
            )
            expense_id = db.add_item(self.year, fee_expense)
            db.edit_item(self.year, transfer_id, transfer, replace(transfer, fee_expense_id=expense_id))

        self.clear_inputs()
        self.refresh_table()

    def delete_item(self, e: ft.Event) -> None:
        """Deletes a transfer from the database."""
        logger.info("Called 'delete_item'")
        transfer_id = e.control.data
        transfer = db.fetch_by_id(self.year, db.WhichDb.TRANSFERS, transfer_id)

        def delete(_: ft.Event) -> None:
            """Actually deletes the transfer."""
            success = db.remove_item(self.year, db.WhichDb.TRANSFERS, transfer_id)
            if not success:
                show_alert(
                    self._page, "Error deleting transfer", f"It was not possible to delete transfer {transfer_id}"
                )
            elif transfer.fee_expense_id is not None:
                db.remove_item(self.year, db.WhichDb.EXPENSES, transfer.fee_expense_id)

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

    def edit_this_item(self, e: ft.Event) -> None:
        """Edits a transfer."""
        logger.info("Called 'edit_this_item'")

        transfer_id = e.control.data
        old_transfer = db.fetch_by_id(self.year, db.WhichDb.TRANSFERS, transfer_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the transfer."""
            new_transfer = self.get_transfer_from_inputs()
            if new_transfer is None:
                return

            fee_expense_id = old_transfer.fee_expense_id
            if old_transfer.fee is None and new_transfer.fee is not None:
                fee_expense = db.Expense(
                    month=new_transfer.month,
                    day_start=new_transfer.day,
                    description=new_transfer.description,
                    category=db.Categories.TRADING_FEE,
                    cost=new_transfer.fee,
                )
                fee_expense_id = db.add_item(self.year, fee_expense)
            elif old_transfer.fee is not None and new_transfer.fee is None:
                db.remove_item(self.year, db.WhichDb.EXPENSES, old_transfer.fee_expense_id)
                fee_expense_id = None
            elif old_transfer.fee is not None and new_transfer.fee is not None:
                old_fee_expense = db.fetch_by_id(self.year, db.WhichDb.EXPENSES, old_transfer.fee_expense_id)
                new_fee_expense = db.Expense(
                    month=new_transfer.month,
                    day_start=new_transfer.day,
                    description=new_transfer.description,
                    category=db.Categories.TRADING_FEE,
                    cost=new_transfer.fee,
                )
                db.edit_item(self.year, old_transfer.fee_expense_id, old_fee_expense, new_fee_expense)

            new_transfer = replace(new_transfer, fee_expense_id=fee_expense_id)

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

        self.fill_inputs_from_transfer(old_transfer, e)

    def copy_this_item(self, e: ft.Event) -> None:
        """Prefills the add-transfer form from an existing transfer, to add it as a new entry."""
        logger.info("Called 'copy_this_item'")
        transfer_id = e.control.data
        transfer = db.fetch_by_id(self.year, db.WhichDb.TRANSFERS, transfer_id)

        self.add_transfer_button.content = "Add Transfer"
        self.add_transfer_button.color = None
        self.add_transfer_button.on_click = self.add_new_transfer

        self.fill_inputs_from_transfer(transfer, e)

    def fill_inputs_from_transfer(self, transfer: db.Transfer, e: ft.Event) -> None:
        """Populates the add-transfer controls with an existing transfer's values."""
        self.date_picker.value = datetime(year=self.year, month=transfer.month, day=transfer.day)
        self.update_date_text(e)
        self.kind_picker.value = str(transfer.kind.value)
        self.amount_text.value = f"{transfer.amount:.2f}"
        self.fee_text.value = f"{transfer.fee:.2f}" if transfer.fee is not None else ""
        self.description_text.value = transfer.description
        self.source_text.value = transfer.source or ""
        self.destination_text.value = transfer.destination or ""

    def _fetch_rows(self) -> db.RowGenerator:
        """Fetches transfers matching the current sort and filters."""
        return db.fetch_transfers(self.year, self.current_sort, self.current_month_filter, self.current_enum_filter)


def transfers_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return TransfersView(page)
