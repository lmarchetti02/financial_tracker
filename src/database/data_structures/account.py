"""Implementation of the `:class:Account` and `:class:AccountBalance` classes."""

from enum import Enum, auto
from logging import getLogger
from sqlite3 import Row
from typing import Self

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from _helpers.constants import ACCOUNT_BALANCES_DB_NAME, ACCOUNTS_DB_NAME
from _helpers.formatting import enum_label, format_amount

from .base import DataContainer

logger = getLogger("financial_tracker")


class AccountKind(Enum):
    """Enum with all the possible kinds of accounts."""

    CASH = auto()
    EMERGENCY = auto()
    INVESTMENTS = auto()
    CRYPTO = auto()
    PENSION = auto()
    DEBT = auto()
    CREDIT = auto()


ACCOUNT_KIND_COLORS = {
    AccountKind.CASH: "#C80000",
    AccountKind.CRYPTO: "#FF8F00",
    AccountKind.EMERGENCY: "#0D47A1",
    AccountKind.INVESTMENTS: "#4CAF50",
    AccountKind.PENSION: "#6A1B9A",
    AccountKind.CREDIT: "#FDD835",
}


@dataclass(frozen=True, kw_only=True)
class Account(DataContainer):
    """Account blueprint.

    Attributes:
        name (str): The name of the account.
        kind (AccountKind): The kind of account. See `:enum:AccountKind`.
        opening_balance (float): The account's true balance immediately before month 1 of the
            year it's stored in. Only meaningful for `:enum:AccountKind.DEBT`/`.CREDIT` accounts,
            whose monthly balances are computed from linked transfers rather than typed in by
            hand — this is the one manually-set starting point that computation builds on top of.
            Defaults to 0.0.
        is_card (bool): Whether this account is a credit card, i.e. an `:enum:AccountKind.DEBT`
            account that expenses can be paid with (see `:attr:Expense.paid_with`), each one
            raising its computed balance. Only allowed on Debt accounts. Defaults to `False`.
    """

    db_name = ACCOUNTS_DB_NAME

    name: str
    kind: AccountKind
    # These must stay in declaration order, with new fields appended last: `add_missing_columns`
    # always appends new columns to the physical end of an already-existing table, so a field
    # declared anywhere else here would desync `init_from_tuple`'s positional zip for any accounts
    # table that predates it.
    opening_balance: float = 0.0
    is_card: bool = False

    @model_validator(mode="after")
    def card_is_debt(self) -> Self:
        """Validates that only a Debt account can be a credit card."""
        if self.is_card and self.kind is not AccountKind.DEBT:
            raise ValueError("Only a Debt account can be a credit card.")

        return self

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'Account.get_table_columns'")

        return [
            DataColumn2(label=ft.Text("Name"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("Kind"), fixed_width=150),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            ft.DataCell(ft.Text(row["name"])),
            ft.DataCell(ft.Text(enum_label(AccountKind[row["kind"]]))),
        ]


@dataclass(frozen=True, kw_only=True)
class AccountBalance(DataContainer):
    """AccountBalance blueprint: one month-end balance snapshot for an account.

    Attributes:
        account_id (int): The id of the `:class:Account` this balance belongs to.
        month (int): The month of the snapshot (between 1 and 12).
        balance (float): The account's total balance in € at the end of `month`.
    """

    db_name = ACCOUNT_BALANCES_DB_NAME

    account_id: int
    month: int = Field(gt=0, lt=13)
    balance: float

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:  # noqa: D102
        logger.info("Called 'AccountBalance.get_table_columns'")

        return [
            AccountBalance.month_column(),
            DataColumn2(label=ft.Text("Balance (€)"), numeric=True, fixed_width=150),
        ]

    @staticmethod
    def get_table_row(row: Row) -> list[ft.DataCell]:  # noqa: D102
        return [
            AccountBalance.month_cell(row),
            ft.DataCell(ft.Text(format_amount(row["balance"], decimals=0))),
        ]
