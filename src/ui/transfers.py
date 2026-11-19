"""Implementation of the 'transfers' layout."""

from dataclasses import replace
from datetime import datetime
from logging import getLogger
from typing import ClassVar

import flet as ft
from flet_datatable2 import DataColumn2

import database as db
from _helpers.constants import (SYSTEM_CATEGORY_TRADING_FEE,
                                SYSTEM_KIND_INVESTMENT,
                                SYSTEM_SOURCE_INVESTMENTS)
from _helpers.expression_parser import evaluate_expression
from _helpers.formatting import enum_label, format_amount

from .base_view import BaseCrudView
from .colors import TRANSFERS_ACCENT
from .common import DATE_PICKER_LOCALE, show_alert, show_confirm_dialog
from .typography import caption

logger = getLogger("financial_tracker")

# `ft.Dropdown` keys can't be `None`, so "no account" gets a key no account name can collide with
NO_ACCOUNT_KEY = "\x00no-account"
NO_ACCOUNT_LABEL = "None"


class TransfersView(BaseCrudView):
    """Encapsulates the 'transfers' view logic and UI."""

    _title = "Transfers"
    _accent_color = TRANSFERS_ACCENT
    _sorting_config_cls = db.TransfersSortingConfig
    _item_label = "Transfer"
    _form_height: ClassVar[int] = 230

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        # date
        self.date_picker = ft.DatePicker(
            value=self.default_date, locale=DATE_PICKER_LOCALE, on_change=self.update_date_text
        )
        self.date_button = ft.Button(
            content=self.default_date.strftime("%d/%m"),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_date_picker,
            width=150,
        )

        # kind
        kinds = db.fetch_kinds()
        self.kind_picker = ft.Dropdown(
            label="Kind",
            options=[ft.DropdownOption(key=kind, text=kind) for kind in kinds],
            on_text_change=lambda _: setattr(self.kind_picker, "error_text", None),
            on_select=self.handle_kind_change,
            width=200,
        )

        # amount
        self.amount_text = ft.TextField(label="Amount (€)", width=170)

        # source / destination
        self.accounts = [account for _, account in db.fetch_account_definitions(self.location)]
        self.extra_account_names: list[str] = []
        self.source_picker = ft.Dropdown(label="Source", value=NO_ACCOUNT_KEY, width=250)
        self.destination_picker = ft.Dropdown(label="Destination", value=NO_ACCOUNT_KEY, width=250)
        self.new_source_button = self._build_new_account_button(self.source_picker)
        self.new_destination_button = self._build_new_account_button(self.destination_picker)
        self.update_account_pickers()

        # description
        self.description_text = ft.TextField(label="Description", width=350, multiline=True)

        # fee / profit
        self.fee_text = ft.TextField(label="Fee", width=120)
        self.profit_text = ft.TextField(label="Profit", width=120)
        self.update_investment_fields_state()

        # button
        self._build_add_button(self.add_new_transfer)
        self.clear_button = self._build_clear_button()

        # collapsible form
        self.form_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.date_button,
                        ft.Container(width=40),
                        self.kind_picker,
                        ft.Container(width=40),
                        self.amount_text,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Row([self.source_picker, self.new_source_button], spacing=0, tight=True),
                        ft.Container(width=40),
                        ft.Row([self.destination_picker, self.new_destination_button], spacing=0, tight=True),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        self.description_text,
                        ft.Container(width=5),
                        self.fee_text,
                        ft.Container(width=5),
                        self.profit_text,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row([self.add_button, self.clear_button], alignment=ft.MainAxisAlignment.CENTER),
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # data table
        columns = db.Transfer.get_table_columns()
        columns.append(DataColumn2(label=ft.Text("Options"), fixed_width=150))
        columns[0].on_sort = self.sort_columns
        columns[6].on_sort = self.sort_columns

        columns[0].label.controls.append(self._build_month_filter_menu())  # type: ignore
        columns[2].label.controls.append(self._build_lookup_filter_menu(kinds, "Filter kind"))  # type: ignore

        self.data_table = self._build_data_table(columns)
        self.table_column = ft.Column(controls=[self.data_table], expand=True, scroll=ft.ScrollMode.AUTO)

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""
        return [
            ft.Container(height=5),
            ft.Row([self.toggle_form_button], alignment=ft.MainAxisAlignment.CENTER),
            self.form_container,
            ft.Container(height=5),
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

    def update_investment_fields_state(self) -> None:
        """Enables the fee/profit fields only when the selected kind is the investment kind."""
        is_investment = self.kind_picker.value == SYSTEM_KIND_INVESTMENT
        self.fee_text.disabled = not is_investment
        self.profit_text.disabled = not is_investment

    def handle_kind_change(self, _: ft.Event) -> None:
        """Clears the kind error text and updates the fee/profit fields' enabled state."""
        self.kind_picker.error_text = None

        self.update_investment_fields_state()
        if self.fee_text.disabled:
            self.fee_text.value = ""
        if self.profit_text.disabled:
            self.profit_text.value = ""

        self.update_account_pickers()

        self._page.update()

    def _offered_account_names(self) -> list[str]:
        """Returns the names of the accounts the selected kind may name in its source/destination.

        A Debt/Credit transfer may only name accounts of the matching kind (any other one would be
        refused by `db.sync_transfer_accounts`); every other kind may name any account of the year.
        """
        kind = db.debt_credit_account_kind(self.kind_picker.value)
        return [account.name for account in self.accounts if kind is None or account.kind is kind]

    def update_account_pickers(self) -> None:
        """Offers the accounts the selected kind may name, resetting any selection no longer offered."""
        names = self._offered_account_names()
        names += [name for name in self.extra_account_names if name not in names]

        for picker in (self.source_picker, self.destination_picker):
            # each dropdown needs its own option controls, so they're built per picker
            picker.options = [ft.DropdownOption(key=NO_ACCOUNT_KEY, text=NO_ACCOUNT_LABEL)] + [
                ft.DropdownOption(key=name, text=name) for name in names
            ]
            if picker.value not in names:
                picker.value = NO_ACCOUNT_KEY

        kind = db.debt_credit_account_kind(self.kind_picker.value)
        for button in (self.new_source_button, self.new_destination_button):
            button.disabled = kind is None
            button.tooltip = (
                f"New {enum_label(kind)} account" if kind is not None else "Choose the Debt or Credit kind to add an account"
            )

    def _account_key(self, name: str | None) -> str:
        """Returns the source/destination picker key showing `name`.

        Account names match case-insensitively (as when computing a Debt/Credit balance), so a
        transfer stored as "mom" still selects the "Mom" account.
        """
        if name is None:
            return NO_ACCOUNT_KEY

        for account in self.accounts:
            if account.name.lower() == name.lower():
                return account.name

        return name

    def _build_new_account_button(self, picker: ft.Dropdown) -> ft.IconButton:
        """Builds the "+" button creating a new Debt/Credit account and selecting it in `picker`."""
        return ft.IconButton(icon=ft.Icons.ADD, on_click=lambda _: self.open_new_account_dialog(picker))

    def open_new_account_dialog(self, picker: ft.Dropdown) -> None:
        """Shows a dialog creating an account of the selected Debt/Credit kind, then selects it in `picker`."""
        logger.info("Called 'open_new_account_dialog'")

        kind = db.debt_credit_account_kind(self.kind_picker.value)
        if kind is None:
            return

        owed = "you owe" if kind is db.AccountKind.DEBT else "you are owed"
        name_field = ft.TextField(label="Name", autofocus=True)
        balance_field = ft.TextField(label="Opening balance (€)", hint_text="0")

        def create(_: ft.Event) -> None:
            """Creates the account, if valid, and selects it."""
            name_field.error_text = None
            balance_field.error_text = None

            name = (name_field.value or "").strip()
            if not name:
                name_field.error_text = "You must give the account a name."
                self._page.update()
                return

            try:
                opening_balance = evaluate_expression(balance_field.value) if balance_field.value else 0.0
            except ValueError:
                balance_field.error_text = "Must be a number or an arithmetic expression."
                self._page.update()
                return

            try:
                db.create_account(self.location, db.Account(name=name, kind=kind, opening_balance=opening_balance))
            except ValueError as error:
                name_field.error_text = str(error)
                self._page.update()
                return

            self._page.pop_dialog()

            self.accounts = [account for _, account in db.fetch_account_definitions(self.location)]
            self.update_account_pickers()
            picker.value = name
            self._page.update()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"New {enum_label(kind)} account"),
                content=ft.Column(
                    controls=[
                        caption(f"Opening balance: what {owed} at the start of {self.location.year}."),
                        name_field,
                        balance_field,
                    ],
                    tight=True,
                    width=350,
                ),
                actions=[
                    ft.TextButton("Create", on_click=create),
                    ft.TextButton("Cancel", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def get_transfer_from_inputs(self) -> db.Transfer | None:
        """Reads the values in the controls and returns a `:class:Transfer` object."""
        logger.info("Called 'get_transfer_from_inputs'")

        if self.date_picker.value is None:
            show_alert(self._page, "Empty date", "You must select a date")
            return None

        if self.description_text.value == "":
            show_alert(self._page, "Empty description", "You must add a description to the transfer")
            return None

        if self.kind_picker.value is None:
            self.kind_picker.error_text = "You must choose a kind"
            self._page.update()
            return None

        if self.amount_text.value == "":
            show_alert(self._page, "Empty amount", "You must add an amount to the transfer")
            return None

        amount = self._parse_amount_field(self.amount_text.value, "Invalid amount", "amount")
        if amount is None:
            return None

        source = None if self.source_picker.value == NO_ACCOUNT_KEY else self.source_picker.value
        destination = None if self.destination_picker.value == NO_ACCOUNT_KEY else self.destination_picker.value
        if source is None and destination is None:
            show_alert(
                self._page,
                "Missing source/destination",
                "A transfer must have a source or a destination.",
            )
            return None

        parsed_fee = self._parse_optional_positive_amount(self.fee_text.value or "", "Invalid fee", "fee")
        if parsed_fee is None:
            return None
        fee, fee_expression = parsed_fee

        parsed_profit = self._parse_optional_positive_amount(self.profit_text.value or "", "Invalid profit", "profit")
        if parsed_profit is None:
            return None
        profit, profit_expression = parsed_profit

        date_local = self.date_picker.value.astimezone()

        transfer = db.Transfer(
            month=date_local.month,
            day=date_local.day,
            kind=self.kind_picker.value,
            description=self.description_text.value,
            source=source,
            destination=destination,
            amount=amount,
            amount_expression=self.amount_text.value,
            fee=fee,
            fee_expression=fee_expression,
            profit=profit,
            profit_expression=profit_expression,
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
        self.profit_text.value = ""
        self.update_investment_fields_state()
        self.extra_account_names = []
        self.source_picker.value = NO_ACCOUNT_KEY
        self.destination_picker.value = NO_ACCOUNT_KEY
        self.update_account_pickers()
        logger.debug("Cleared transfer data")

    def _sync_transfer_accounts(self, *transfers: db.Transfer) -> None:
        """Syncs the Debt/Credit account(s) for each transfer, warning about any newly created one."""
        created: list[str] = []
        try:
            for transfer in transfers:
                created += db.sync_transfer_accounts(self.location, transfer)
        except ValueError as error:
            show_alert(self._page, "Account mismatch", str(error))
            return

        if created:
            show_alert(
                self._page,
                "New account created — review its opening balance",
                f"Assumed €0 as the starting balance for: {', '.join(sorted(set(created)))}. If "
                "any of these already owed/were owed something before this transfer, set the "
                "correct opening balance via the 'previous year' column in Accounts.",
            )

    def add_new_transfer(self, _: ft.Event) -> None:
        """Adds a new transfer based on the user's inputs."""
        logger.info("Called 'add_new_transfer'")

        transfer = self.get_transfer_from_inputs()
        if transfer is None:
            return

        transfer_id = db.add_item(self.location, transfer)

        linked_ids: dict[str, int] = {}
        if transfer.fee is not None:
            linked_ids["fee_expense_id"] = db.add_item(self.location, self._fee_expense_for(transfer))
        if transfer.profit is not None:
            linked_ids["profit_income_id"] = db.add_item(self.location, self._profit_income_for(transfer))
        if linked_ids:
            db.edit_item(self.location, transfer_id, transfer, replace(transfer, **linked_ids))

        self._sync_transfer_accounts(transfer)

        self.clear_inputs()
        self._set_form_expanded(False)
        self.refresh_table()

    def delete_item(self, e: ft.Event) -> None:
        """Deletes a transfer from the database."""
        logger.info("Called 'delete_item'")
        transfer_id = e.control.data
        transfer = db.fetch_by_id(self.location, db.WhichDb.TRANSFERS, transfer_id)

        def delete(_: ft.Event) -> None:
            """Actually deletes the transfer."""
            # close this dialog first: `pop_dialog` closes the most recent one, which would be the alert
            self._page.pop_dialog()

            success = db.remove_item(self.location, db.WhichDb.TRANSFERS, transfer_id)
            if not success:
                show_alert(
                    self._page, "Error deleting transfer", f"It was not possible to delete transfer {transfer_id}"
                )
            else:
                if transfer.fee_expense_id is not None:
                    db.remove_item(self.location, db.WhichDb.EXPENSES, transfer.fee_expense_id)
                if transfer.profit_income_id is not None:
                    db.remove_item(self.location, db.WhichDb.INCOMES, transfer.profit_income_id)

                self._sync_transfer_accounts(transfer)

            self.refresh_table()

        show_confirm_dialog(self._page, "Delete transfer", "Are you sure you want to delete this transfer?", delete)

    def edit_this_item(self, e: ft.Event) -> None:
        """Edits a transfer."""
        logger.info("Called 'edit_this_item'")

        transfer_id = e.control.data
        old_transfer = db.fetch_by_id(self.location, db.WhichDb.TRANSFERS, transfer_id)

        def modify(_: ft.Event) -> None:
            """Actually modifies the transfer."""
            new_transfer = self.get_transfer_from_inputs()
            if new_transfer is None:
                return

            fee_expense_id = old_transfer.fee_expense_id
            if old_transfer.fee is None and new_transfer.fee is not None:
                fee_expense_id = db.add_item(self.location, self._fee_expense_for(new_transfer))
            elif old_transfer.fee is not None and new_transfer.fee is None:
                db.remove_item(self.location, db.WhichDb.EXPENSES, old_transfer.fee_expense_id)
                fee_expense_id = None
            elif old_transfer.fee is not None and new_transfer.fee is not None:
                old_fee_expense = db.fetch_by_id(self.location, db.WhichDb.EXPENSES, old_transfer.fee_expense_id)
                new_fee_expense = self._fee_expense_for(new_transfer)
                db.edit_item(self.location, old_transfer.fee_expense_id, old_fee_expense, new_fee_expense)

            profit_income_id = old_transfer.profit_income_id
            if old_transfer.profit is None and new_transfer.profit is not None:
                profit_income_id = db.add_item(self.location, self._profit_income_for(new_transfer))
            elif old_transfer.profit is not None and new_transfer.profit is None:
                db.remove_item(self.location, db.WhichDb.INCOMES, old_transfer.profit_income_id)
                profit_income_id = None
            elif old_transfer.profit is not None and new_transfer.profit is not None:
                old_profit_income = db.fetch_by_id(self.location, db.WhichDb.INCOMES, old_transfer.profit_income_id)
                new_profit_income = self._profit_income_for(new_transfer)
                db.edit_item(self.location, old_transfer.profit_income_id, old_profit_income, new_profit_income)

            new_transfer = replace(new_transfer, fee_expense_id=fee_expense_id, profit_income_id=profit_income_id)

            if new_transfer == old_transfer:
                show_alert(self._page, "Unchanged transfer", "You did not modify the transfer.")
                return

            success = db.edit_item(self.location, transfer_id, old_transfer, new_transfer)
            if not success:
                show_alert(
                    self._page, "Error modifying transfer", f"It was not possible to modify transfer {transfer_id}"
                )
            else:
                self._sync_transfer_accounts(old_transfer, new_transfer)

            self.clear_inputs()
            self.reset_add_button()
            self._set_form_expanded(False)

            self.refresh_table()

        self._enter_edit_mode(modify)

        self._set_form_expanded(True)
        self.fill_inputs_from_transfer(old_transfer, e)

    def copy_this_item(self, e: ft.Event) -> None:
        """Prefills the add-transfer form from an existing transfer, to add it as a new entry."""
        logger.info("Called 'copy_this_item'")
        transfer_id = e.control.data
        transfer = db.fetch_by_id(self.location, db.WhichDb.TRANSFERS, transfer_id)

        self.reset_add_button()

        self._set_form_expanded(True)
        self.fill_inputs_from_transfer(transfer, e)

    @staticmethod
    def _fee_expense_for(transfer: db.Transfer) -> db.Expense:
        """Builds the linked `:class:Expense` logging `transfer`'s fee under the trading-fee category."""
        return db.Expense(
            month=transfer.month,
            day_start=transfer.day,
            description=transfer.description,
            category=SYSTEM_CATEGORY_TRADING_FEE,
            cost=transfer.fee,  # type: ignore
        )

    @staticmethod
    def _profit_income_for(transfer: db.Transfer) -> db.Income:
        """Builds the linked `:class:Income` logging `transfer`'s profit under the investments source."""
        return db.Income(
            month=transfer.month,
            source=SYSTEM_SOURCE_INVESTMENTS,
            description=transfer.description,
            amount=transfer.profit,  # type: ignore
        )

    def fill_inputs_from_transfer(self, transfer: db.Transfer, e: ft.Event) -> None:
        """Populates the add-transfer controls with an existing transfer's values."""
        self.date_picker.value = datetime(year=self.location.year, month=transfer.month, day=transfer.day)
        self.kind_picker.value = transfer.kind
        self.update_investment_fields_state()
        self.amount_text.value = (
            transfer.amount_expression if transfer.amount_expression is not None else format_amount(transfer.amount)
        )
        if transfer.fee is not None:
            self.fee_text.value = (
                transfer.fee_expression if transfer.fee_expression is not None else format_amount(transfer.fee)
            )
        else:
            self.fee_text.value = ""
        if transfer.profit is not None:
            self.profit_text.value = (
                transfer.profit_expression if transfer.profit_expression is not None else format_amount(transfer.profit)
            )
        else:
            self.profit_text.value = ""
        self.description_text.value = transfer.description

        # a stored name no longer offered (e.g. of a deleted account) stays selectable rather than being lost on save
        keys = [self._account_key(transfer.source), self._account_key(transfer.destination)]
        offered = self._offered_account_names()
        self.extra_account_names = [key for key in dict.fromkeys(keys) if key != NO_ACCOUNT_KEY and key not in offered]
        self.update_account_pickers()
        self.source_picker.value, self.destination_picker.value = keys
        self.update_date_text(e)

    def _fetch_rows(self) -> db.RowGenerator:
        """Fetches transfers matching the current sort and filters."""
        return db.fetch_transfers(self.location, self.current_sort, self.current_month_filter, self.current_lookup_filter)


def transfers_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return TransfersView(page)
