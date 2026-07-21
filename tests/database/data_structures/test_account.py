"""Unit tests for `database.data_structures.account`."""

import pytest

from database.data_structures.account import Account, AccountBalance, AccountKind


def make_account(**overrides: object) -> Account:
    """Builds an `:class:Account` with sensible defaults, overridden by `overrides`."""
    defaults = {"name": "Checking", "kind": AccountKind.CASH}
    defaults.update(overrides)
    return Account(**defaults)


def make_balance(**overrides: object) -> AccountBalance:
    """Builds an `:class:AccountBalance` with sensible defaults, overridden by `overrides`."""
    defaults = {"account_id": 1, "month": 1, "balance": 100.0}
    defaults.update(overrides)
    return AccountBalance(**defaults)


class TestAccount:
    """Tests for `Account`."""

    def test_construction_succeeds_with_valid_fields(self) -> None:
        """A name and kind are enough to build an account."""
        account = make_account(name="Savings", kind=AccountKind.EMERGENCY)

        assert account.name == "Savings"
        assert account.kind == AccountKind.EMERGENCY


class TestAccountGetTableColumns:
    """Tests for `Account.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for name and kind."""
        assert len(Account.get_table_columns()) == 2


class TestAccountGetTableRow:
    """Tests for `Account.get_table_row`."""

    def test_formats_the_name_and_kind(self) -> None:
        """The kind is rendered as a human-readable label."""
        row = {"name": "Checking", "kind": "CASH"}

        cells = Account.get_table_row(row)

        assert cells[0].content.value == "Checking"
        assert cells[1].content.value == "Cash"


class TestAccountBalance:
    """Tests for `AccountBalance`."""

    @pytest.mark.parametrize("month", [0, 13])
    def test_construction_fails_for_out_of_range_month(self, month: int) -> None:
        """A month outside 1-12 is rejected."""
        with pytest.raises(ValueError):
            make_balance(month=month)

    def test_construction_succeeds_with_a_negative_balance(self) -> None:
        """A negative balance (e.g. a loan or credit account) is valid."""
        balance = make_balance(balance=-50.0)

        assert balance.balance == -50.0


class TestAccountBalanceGetTableColumns:
    """Tests for `AccountBalance.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for month and balance."""
        assert len(AccountBalance.get_table_columns()) == 2


class TestAccountBalanceGetTableRow:
    """Tests for `AccountBalance.get_table_row`."""

    def test_formats_the_month_and_balance(self) -> None:
        """The month and balance are formatted for display."""
        row = {"month": 3, "balance": 1234.5}

        cells = AccountBalance.get_table_row(row)

        assert cells[0].content.content.value == "3"
        assert cells[1].content.value == "1234.50"
