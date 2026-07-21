"""Implementation of the accounts layout."""

from logging import getLogger

import flet as ft
from flet_datatable2 import DataColumn2, DataTable2

import database as db
from _helpers.constants import MONTHS
from _helpers.formatting import enum_label

from .common import build_styled_data_table, show_alert

logger = getLogger("financial_tracker")

_HEADING_COLOR = "#B8860B"
_ACCOUNT_COLUMN_WIDTH = 180
_ACCOUNT_DIVIDER = ft.Border(right=ft.BorderSide(width=2))
_HEADING_ROW_HEIGHT = 35
_BALANCE_ROW_HEIGHT = 48
_ACCOUNT_COLORS = {
    db.AccountKind.CASH: "#C80000",
    db.AccountKind.CRYPTO: "#FF8F00",
    db.AccountKind.EMERGENCY: "#0D47A1",
    db.AccountKind.INVESTMENTS: "#4CAF50",
    db.AccountKind.PENSION: "#6A1B9A",
}

_KIND_OPTIONS = [
    ft.DropdownOption(key=str(kind.value), text=enum_label(kind))
    for kind in sorted(db.AccountKind, key=lambda k: k.name)
]


class AccountsView(ft.Column):
    """Encapsulates the accounts view: manage accounts and log their monthly balances."""

    def __init__(self, page: ft.Page) -> None:
        """Initializes the view, state variables, and layout."""
        super().__init__()
        logger.info("Called 'AccountsView.__init__'")
        self._page = page

        if (year := self._page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")
        self.year = int(year)

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.scroll = ft.ScrollMode.AUTO

        self._init_controls()
        self.controls = self._build_layout()
        self.refresh()

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        self.name_text = ft.TextField(label="Account name", width=250)
        self.kind_dropdown = ft.Dropdown(label="Kind", options=_KIND_OPTIONS, width=200)
        self.add_account_button = ft.Button("Add account", on_click=self.add_account)

        self.accounts_table = build_styled_data_table(
            [DataColumn2(label=ft.Text("Name")), DataColumn2(label=ft.Text("Kind")), DataColumn2(label=ft.Text(""))],
            [],
            _HEADING_COLOR,
        )
        self.balance_grid_container = ft.Column()

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout."""
        return [
            ft.Container(height=20),
            ft.Text("Monthly balances (€)", size=20, weight=ft.FontWeight.BOLD),
            self.balance_grid_container,
            ft.Container(height=20),
            ft.Text("Accounts", size=20, weight=ft.FontWeight.BOLD),
            ft.Row(
                controls=[self.name_text, self.kind_dropdown, self.add_account_button],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            self.accounts_table,
        ]

    def add_account(self, _: ft.Event) -> None:
        """Adds a new account based on the user's inputs."""
        logger.info("Called 'add_account'")

        name = (self.name_text.value or "").strip()
        if not name:
            show_alert(self._page, "Empty name", "You must give the account a name.")
            return

        if self.kind_dropdown.value is None:
            show_alert(self._page, "Missing kind", "You must choose a kind for the account.")
            return

        account = db.Account(name=name, kind=db.AccountKind(int(self.kind_dropdown.value)))
        db.add_item(self.year, account)
        logger.debug(f"Added account:\n{account}")

        self.name_text.value = ""
        self.kind_dropdown.value = None
        self.refresh()

    def delete_account(self, e: ft.Event) -> None:
        """Deletes an account and every balance logged for it."""
        logger.info("Called 'delete_account'")
        account_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the account."""
            db.delete_account(self.year, account_id)
            self._page.pop_dialog()
            self.refresh()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete account"),
                content=ft.Text("Are you sure? Every balance logged for this account will be deleted too."),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def commit_cell(self, e: ft.Event) -> None:
        """Persists (or clears) the balance for the cell that was just edited."""
        logger.info("Called 'commit_cell'")
        account_id, month = e.control.data
        raw_value = (e.control.value or "").strip()

        if raw_value == "":
            db.delete_balance(self.year, account_id, month)
            self.balances.pop((account_id, month), None)
            return

        try:
            balance = float(raw_value.replace(",", "."))
        except ValueError:
            show_alert(self._page, "Invalid balance", "The balance must be a real number (comma for decimals allowed).")
            old_value = self.balances.get((account_id, month))
            e.control.value = f"{old_value:.0f}" if old_value is not None else ""
            self._page.update()
            return

        db.save_balance(self.year, account_id, month, balance)
        logger.debug(f"Saved balance for account {account_id}, month {month}: {balance}")

        self.balances[(account_id, month)] = balance
        e.control.value = f"{balance:.0f}"
        self._page.update()

    def commit_previous_year_cell(self, e: ft.Event) -> None:
        """Persists (or clears) the previous year's December balance, syncing it to that year's db."""
        logger.info("Called 'commit_previous_year_cell'")
        account_name, account_kind = e.control.data
        raw_value = (e.control.value or "").strip()

        if raw_value == "":
            db.delete_previous_year_end_balance(self.year, account_name)
            self.previous_year_balances.pop(account_name, None)
            return

        try:
            balance = float(raw_value.replace(",", "."))
        except ValueError:
            show_alert(self._page, "Invalid balance", "The balance must be a real number (comma for decimals allowed).")
            old_value = self.previous_year_balances.get(account_name)
            e.control.value = f"{old_value:.0f}" if old_value is not None else ""
            self._page.update()
            return

        db.save_previous_year_end_balance(self.year, account_name, account_kind, balance)
        logger.debug(f"Saved {self.year - 1} December balance for '{account_name}': {balance}")

        self.previous_year_balances[account_name] = balance
        e.control.value = f"{balance:.0f}"
        self._page.update()

    def refresh(self) -> None:
        """Reloads the accounts and their balances, and rebuilds both tables."""
        logger.info("Called 'refresh'")

        self.accounts = db.fetch_account_definitions(self.year)
        self.balances = db.fetch_account_balances(self.year)
        self.previous_year_balances = db.fetch_previous_year_end_balances(self.year)

        self.accounts_table.rows = self._build_accounts_rows()
        self.balance_grid_container.controls = [self._build_balance_grid()]

        self._page.update()

    def _build_accounts_rows(self) -> list[ft.DataRow]:
        """Builds the rows of the accounts-management table."""
        rows = []
        for account_id, account in self.accounts:
            delete_button = ft.Button(
                icon=ft.Icons.DELETE, width=50, height=30, data=account_id, on_click=self.delete_account
            )
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(account.name)),
                        ft.DataCell(
                            ft.Text(enum_label(account.kind), color=_ACCOUNT_COLORS.get(account.kind, "#000000"))
                        ),
                        ft.DataCell(delete_button),
                    ]
                )
            )
        return rows

    def _build_balance_grid(self) -> ft.Control:
        """Builds the editable account x month balance grid."""
        if not self.accounts:
            return ft.Text("Add an account above to start logging balances.")

        columns = [
            DataColumn2(
                label=ft.Container(
                    ft.Text("Account"),
                    width=_ACCOUNT_COLUMN_WIDTH,
                    height=_HEADING_ROW_HEIGHT,
                    alignment=ft.Alignment.CENTER_LEFT,
                    border=_ACCOUNT_DIVIDER,
                ),
                fixed_width=_ACCOUNT_COLUMN_WIDTH,
            ),
            DataColumn2(label=ft.Text(str(self.year - 1)), numeric=True, fixed_width=110),
        ]
        columns += [DataColumn2(label=ft.Text(month), numeric=True, fixed_width=110) for month in MONTHS]

        rows = []
        for account_id, account in self.accounts:
            account_cell = ft.DataCell(
                ft.Container(
                    ft.Text(account.name, color=_ACCOUNT_COLORS.get(account.kind, "#000000")),
                    width=_ACCOUNT_COLUMN_WIDTH,
                    height=_BALANCE_ROW_HEIGHT,
                    alignment=ft.Alignment.CENTER_LEFT,
                    border=_ACCOUNT_DIVIDER,
                    padding=ft.Padding(left=10, top=0, right=10, bottom=0),
                )
            )

            previous_year_value = self.previous_year_balances.get(account.name)
            previous_year_cell = ft.DataCell(
                ft.TextField(
                    value=f"{previous_year_value:.0f}" if previous_year_value is not None else "",
                    text_align=ft.TextAlign.RIGHT,
                    border=ft.InputBorder.NONE,
                    content_padding=6,
                    dense=True,
                    data=(account.name, account.kind),
                    on_blur=self.commit_previous_year_cell,
                    on_submit=self.commit_previous_year_cell,
                )
            )

            cells = [account_cell, previous_year_cell]
            for month in range(1, 13):
                value = self.balances.get((account_id, month))
                cells.append(
                    ft.DataCell(
                        ft.TextField(
                            value=f"{value:.0f}" if value is not None else "",
                            text_align=ft.TextAlign.RIGHT,
                            border=ft.InputBorder.NONE,
                            content_padding=6,
                            dense=True,
                            data=(account_id, month),
                            on_blur=self.commit_cell,
                            on_submit=self.commit_cell,
                        )
                    )
                )
            rows.append(ft.DataRow(cells=cells))

        borders = ft.BorderSide(width=2)
        v_lines = ft.BorderSide(width=1, color=ft.Colors.GREY)

        return DataTable2(
            columns=columns,  # type: ignore
            rows=rows,
            fixed_left_columns=1,
            fixed_top_rows=1,
            border=ft.Border(top=borders, bottom=borders, right=borders, left=borders),
            vertical_lines=v_lines,
            horizontal_lines=v_lines,
            heading_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            heading_row_color=_HEADING_COLOR,
            heading_row_height=_HEADING_ROW_HEIGHT,
            data_row_height=_BALANCE_ROW_HEIGHT,
            horizontal_margin=10,
            column_spacing=5,
        )


def accounts_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return AccountsView(page)
