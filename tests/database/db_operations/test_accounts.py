"""Unit tests for `database.db_operations.accounts`."""

import pytest

from database.data_structures.account import Account, AccountKind
from database.db_operations.accounts import (
    delete_account,
    delete_balance,
    delete_previous_year_end_balance,
    fetch_account_balances,
    fetch_account_definitions,
    fetch_previous_year_account_ids,
    fetch_previous_year_end_balances,
    save_balance,
    save_previous_year_end_balance,
    seed_accounts_for_new_year,
)
from database.db_operations.generic import WhichDb, add_item, fetch_by_id, initialize_db

YEAR = 2024
PRIOR_YEAR = 2023


def make_account(**overrides: object) -> Account:
    """Builds an `:class:Account` with sensible defaults, overridden by `overrides`."""
    defaults = {"name": "Checking", "kind": AccountKind.CASH}
    defaults.update(overrides)
    return Account(**defaults)


class TestFetchAccountDefinitions:
    """Tests for `fetch_account_definitions`."""

    def test_orders_by_name_within_the_same_kind(self) -> None:
        """Accounts of the same kind are ordered alphabetically by name."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        add_item(YEAR, make_account(name="Zeta"))
        add_item(YEAR, make_account(name="Alpha"))

        names = [account.name for _, account in fetch_account_definitions(YEAR)]

        assert names == ["Alpha", "Zeta"]

    def test_orders_by_kind_before_name(self) -> None:
        """Accounts are grouped by kind first, even when that reorders their names."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        add_item(YEAR, make_account(name="Alpha", kind=AccountKind.PENSION))
        add_item(YEAR, make_account(name="Zeta", kind=AccountKind.CASH))

        names = [account.name for _, account in fetch_account_definitions(YEAR)]

        assert names == ["Zeta", "Alpha"]


class TestFetchAccountBalances:
    """Tests for `fetch_account_balances`."""

    def test_maps_account_id_and_month_to_the_logged_balance(self) -> None:
        """Every logged snapshot is keyed by `(account_id, month)`."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(YEAR, make_account())

        save_balance(YEAR, account_id, 1, 100.0)
        save_balance(YEAR, account_id, 2, 200.0)

        assert fetch_account_balances(YEAR) == {(account_id, 1): 100.0, (account_id, 2): 200.0}


class TestSaveBalance:
    """Tests for `save_balance`."""

    def test_inserts_a_new_snapshot(self) -> None:
        """A month with no existing snapshot gets a new row."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(YEAR, make_account())

        save_balance(YEAR, account_id, 1, 100.0)

        assert fetch_account_balances(YEAR) == {(account_id, 1): 100.0}

    def test_updates_an_existing_snapshot_instead_of_duplicating_it(self) -> None:
        """Saving the same account/month twice updates the row rather than inserting another."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(YEAR, make_account())

        save_balance(YEAR, account_id, 1, 100.0)
        save_balance(YEAR, account_id, 1, 150.0)

        assert fetch_account_balances(YEAR) == {(account_id, 1): 150.0}


class TestDeleteBalance:
    """Tests for `delete_balance`."""

    def test_removes_an_existing_snapshot(self) -> None:
        """A logged balance is gone after being deleted."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(YEAR, make_account())
        save_balance(YEAR, account_id, 1, 100.0)

        delete_balance(YEAR, account_id, 1)

        assert fetch_account_balances(YEAR) == {}

    def test_is_a_harmless_no_op_for_a_nonexistent_snapshot(self) -> None:
        """Deleting a month that was never logged does not raise."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)

        delete_balance(YEAR, 999, 1)  # must not raise


class TestDeleteAccount:
    """Tests for `delete_account`."""

    def test_deletes_the_account_and_every_balance_logged_for_it(self) -> None:
        """Deleting an account cascades to remove its balance snapshots too."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(YEAR, make_account())
        save_balance(YEAR, account_id, 1, 100.0)
        save_balance(YEAR, account_id, 2, 200.0)

        assert delete_account(YEAR, account_id) is True
        assert fetch_account_balances(YEAR) == {}
        with pytest.raises(ValueError, match="No item with id"):
            fetch_by_id(YEAR, WhichDb.ACCOUNTS, account_id)

    def test_returns_false_for_a_nonexistent_account(self) -> None:
        """Deleting an id that doesn't exist returns `False` instead of raising."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)

        assert delete_account(YEAR, 999) is False


class TestSeedAccountsForNewYear:
    """Tests for `seed_accounts_for_new_year`."""

    def test_is_a_no_op_when_no_prior_year_exists(self) -> None:
        """With no earlier year's database around, the current year is left untouched."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(YEAR)

        assert fetch_account_definitions(YEAR) == []

    def test_copies_account_names_and_kinds_from_the_most_recent_prior_year(self) -> None:
        """Accounts (but not balances) are carried over from the latest year that has any."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        prior_account_id = add_item(PRIOR_YEAR, make_account(name="Savings", kind=AccountKind.EMERGENCY))
        save_balance(PRIOR_YEAR, prior_account_id, 12, 5000.0)
        initialize_db(YEAR, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(YEAR)

        copied = [account for _, account in fetch_account_definitions(YEAR)]
        assert len(copied) == 1
        assert copied[0].name == "Savings"
        assert copied[0].kind == AccountKind.EMERGENCY

    def test_does_not_copy_balances(self) -> None:
        """Only the account definitions are seeded, never the logged balances."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        initialize_db(YEAR, WhichDb.ACCOUNT_BALANCES)
        prior_account_id = add_item(PRIOR_YEAR, make_account())
        save_balance(PRIOR_YEAR, prior_account_id, 1, 100.0)

        seed_accounts_for_new_year(YEAR)

        assert fetch_account_balances(YEAR) == {}

    def test_is_a_no_op_when_the_current_year_already_has_accounts(self) -> None:
        """Existing accounts for the current year are never duplicated from a prior year."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        add_item(PRIOR_YEAR, make_account(name="Old"))
        initialize_db(YEAR, WhichDb.ACCOUNTS)
        add_item(YEAR, make_account(name="Existing"))

        seed_accounts_for_new_year(YEAR)

        names = [account.name for _, account in fetch_account_definitions(YEAR)]
        assert names == ["Existing"]


class TestFetchPreviousYearAccountIds:
    """Tests for `fetch_previous_year_account_ids`."""

    def test_is_empty_when_the_previous_year_has_no_database(self) -> None:
        """With no `year - 1` database file at all, there is nothing to match against."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)

        assert fetch_previous_year_account_ids(YEAR) == {}

    def test_maps_account_names_to_their_id_in_the_previous_year(self) -> None:
        """Each account name in `year - 1` resolves to its id there."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        prior_id = add_item(PRIOR_YEAR, make_account(name="Checking"))

        assert fetch_previous_year_account_ids(YEAR) == {"Checking": prior_id}


class TestFetchPreviousYearEndBalances:
    """Tests for `fetch_previous_year_end_balances`."""

    def test_is_empty_when_the_previous_year_has_no_database(self) -> None:
        """With no `year - 1` database file at all, there is nothing to report."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)

        assert fetch_previous_year_end_balances(YEAR) == {}

    def test_only_includes_accounts_with_a_logged_december_balance(self) -> None:
        """An account that exists in `year - 1` but has no December balance is excluded."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        logged_id = add_item(PRIOR_YEAR, make_account(name="Checking"))
        add_item(PRIOR_YEAR, make_account(name="Savings"))
        save_balance(PRIOR_YEAR, logged_id, 12, 999.0)

        assert fetch_previous_year_end_balances(YEAR) == {"Checking": 999.0}


class TestSavePreviousYearEndBalance:
    """Tests for `save_previous_year_end_balance`."""

    def test_saves_into_the_previous_year_s_database_by_matching_name(self) -> None:
        """The balance is written as month 12 of the matching account in `year - 1`."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_YEAR, make_account(name="Checking"))

        save_previous_year_end_balance(YEAR, "Checking", AccountKind.CASH, 999.0)

        assert fetch_account_balances(PRIOR_YEAR) == {(prior_id, 12): 999.0}

    def test_updates_an_existing_december_balance_instead_of_duplicating_it(self) -> None:
        """Saving twice updates the same row rather than inserting another."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_YEAR, make_account(name="Checking"))

        save_previous_year_end_balance(YEAR, "Checking", AccountKind.CASH, 100.0)
        save_previous_year_end_balance(YEAR, "Checking", AccountKind.CASH, 150.0)

        assert fetch_account_balances(PRIOR_YEAR) == {(prior_id, 12): 150.0}

    def test_creates_the_account_when_the_previous_year_s_database_exists_but_lacks_it(self) -> None:
        """A matching account is created in `year - 1` if it isn't there yet."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)

        save_previous_year_end_balance(YEAR, "New Account", AccountKind.CASH, 500.0)

        created = dict(fetch_account_definitions(PRIOR_YEAR))
        assert len(created) == 1
        prior_id, account = next(iter(created.items()))
        assert account.name == "New Account"
        assert account.kind == AccountKind.CASH
        assert fetch_account_balances(PRIOR_YEAR) == {(prior_id, 12): 500.0}

    def test_creates_the_previous_year_s_database_when_it_does_not_exist_at_all(self) -> None:
        """Logging this column never requires the previous year to have been used already."""
        save_previous_year_end_balance(YEAR, "New Account", AccountKind.CRYPTO, 42.0)

        created = dict(fetch_account_definitions(PRIOR_YEAR))
        assert len(created) == 1
        prior_id, account = next(iter(created.items()))
        assert account.name == "New Account"
        assert account.kind == AccountKind.CRYPTO
        assert fetch_account_balances(PRIOR_YEAR) == {(prior_id, 12): 42.0}


class TestDeletePreviousYearEndBalance:
    """Tests for `delete_previous_year_end_balance`."""

    def test_removes_the_december_balance_in_the_previous_year(self) -> None:
        """The matching account's December balance in `year - 1` is deleted."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_YEAR, make_account(name="Checking"))
        save_balance(PRIOR_YEAR, prior_id, 12, 999.0)

        delete_previous_year_end_balance(YEAR, "Checking")

        assert fetch_account_balances(PRIOR_YEAR) == {}

    def test_is_a_harmless_no_op_when_no_matching_account_exists(self) -> None:
        """Deleting for a name with no match in `year - 1` does not raise."""
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_YEAR, WhichDb.ACCOUNT_BALANCES)

        delete_previous_year_end_balance(YEAR, "Nonexistent")  # must not raise
