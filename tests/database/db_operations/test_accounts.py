"""Unit tests for `database.db_operations.accounts`."""

import pytest

from _helpers.constants import DEFAULT_PROFILE_NAME, SYSTEM_KIND_CREDIT, SYSTEM_KIND_DEBT
from database.data_structures.account import Account, AccountKind
from database.data_structures.transfer import Transfer
from database.db_operations.accounts import (
    delete_account,
    delete_balance,
    delete_previous_year_end_balance,
    fetch_account_balances,
    fetch_account_definitions,
    fetch_balances_by_kind,
    fetch_net_worth_components,
    fetch_opening_balances_by_kind,
    fetch_previous_year_account_ids,
    fetch_previous_year_end_balances,
    fetch_previous_year_end_net_worth_components,
    get_or_create_debt_credit_account,
    recompute_account_balance,
    recompute_all_debt_credit_balances,
    save_account_opening_balance,
    save_balance,
    save_previous_year_end_balance,
    seed_accounts_for_new_year,
    sync_transfer_accounts,
)
from database.db_operations.generic import DbLocation, WhichDb, add_item, fetch_by_id, initialize_db

YEAR = 2024
PRIOR_YEAR = 2023
LOCATION = DbLocation(YEAR)
PRIOR_LOCATION = DbLocation(PRIOR_YEAR)


def make_account(**overrides: object) -> Account:
    """Builds an `:class:Account` with sensible defaults, overridden by `overrides`."""
    defaults = {"name": "Checking", "kind": AccountKind.CASH}
    defaults.update(overrides)
    return Account(**defaults)


def make_transfer(**overrides: object) -> Transfer:
    """Builds a `:class:Transfer` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "kind": SYSTEM_KIND_DEBT,
        "description": "test transfer",
        "source": "Mom",
        "destination": None,
        "amount": 100.0,
    }
    defaults.update(overrides)
    return Transfer(**defaults)


class TestFetchAccountDefinitions:
    """Tests for `fetch_account_definitions`."""

    def test_orders_by_name_within_the_same_kind(self) -> None:
        """Accounts of the same kind are ordered alphabetically by name."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Zeta"))
        add_item(LOCATION, make_account(name="Alpha"))

        names = [account.name for _, account in fetch_account_definitions(LOCATION)]

        assert names == ["Alpha", "Zeta"]

    def test_orders_by_kind_before_name(self) -> None:
        """Accounts are grouped by kind first, even when that reorders their names."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Alpha", kind=AccountKind.PENSION))
        add_item(LOCATION, make_account(name="Zeta", kind=AccountKind.CASH))

        names = [account.name for _, account in fetch_account_definitions(LOCATION)]

        assert names == ["Zeta", "Alpha"]


class TestFetchAccountBalances:
    """Tests for `fetch_account_balances`."""

    def test_maps_account_id_and_month_to_the_logged_balance(self) -> None:
        """Every logged snapshot is keyed by `(account_id, month)`."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account())

        save_balance(LOCATION, account_id, 1, 100.0)
        save_balance(LOCATION, account_id, 2, 200.0)

        assert fetch_account_balances(LOCATION) == {(account_id, 1): 100.0, (account_id, 2): 200.0}


class TestFetchBalancesByKind:
    """Tests for `fetch_balances_by_kind`."""

    def test_is_empty_when_no_balances_are_logged(self) -> None:
        """With no balances at all, there is nothing to report."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)

        assert fetch_balances_by_kind(LOCATION) == {}

    def test_sums_balances_across_every_account_of_the_same_kind(self) -> None:
        """Two accounts of the same kind contribute to a single combined series."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        first_id = add_item(LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        second_id = add_item(LOCATION, make_account(name="Wallet", kind=AccountKind.CASH))
        save_balance(LOCATION, first_id, 1, 100.0)
        save_balance(LOCATION, second_id, 1, 50.0)

        totals = fetch_balances_by_kind(LOCATION)

        assert totals.keys() == {AccountKind.CASH}
        assert totals[AccountKind.CASH][0] == pytest.approx(150.0)

    def test_keeps_different_kinds_in_separate_series(self) -> None:
        """Accounts of different kinds contribute to independent series."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        cash_id = add_item(LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        pension_id = add_item(LOCATION, make_account(name="Pension Fund", kind=AccountKind.PENSION))
        save_balance(LOCATION, cash_id, 3, 100.0)
        save_balance(LOCATION, pension_id, 3, 900.0)

        totals = fetch_balances_by_kind(LOCATION)

        assert totals[AccountKind.CASH][2] == pytest.approx(100.0)
        assert totals[AccountKind.PENSION][2] == pytest.approx(900.0)

    def test_unlogged_months_default_to_zero(self) -> None:
        """A month with no logged balance for a kind stays at zero, not missing."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account(kind=AccountKind.CASH))
        save_balance(LOCATION, account_id, 6, 100.0)

        totals = fetch_balances_by_kind(LOCATION)

        assert totals[AccountKind.CASH][0] == 0.0
        assert totals[AccountKind.CASH][5] == pytest.approx(100.0)


class TestFetchNetWorthComponents:
    """Tests for `fetch_net_worth_components`."""

    def test_splits_balances_into_liquid_assets_pension_credits_and_debts(self) -> None:
        """Each special kind's balance lands in its own matching component array."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        cash_id = add_item(LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        pension_id = add_item(LOCATION, make_account(name="Pension", kind=AccountKind.PENSION))
        credit_id = add_item(LOCATION, make_account(name="Owed to me", kind=AccountKind.CREDIT))
        debt_id = add_item(LOCATION, make_account(name="Owed by me", kind=AccountKind.DEBT))
        save_balance(LOCATION, cash_id, 1, 100.0)
        save_balance(LOCATION, pension_id, 1, 200.0)
        save_balance(LOCATION, credit_id, 1, 50.0)
        save_balance(LOCATION, debt_id, 1, 25.0)

        liquid_assets, pension, credits, debts = fetch_net_worth_components(LOCATION)

        assert liquid_assets[0] == pytest.approx(100.0)
        assert pension[0] == pytest.approx(200.0)
        assert credits[0] == pytest.approx(50.0)
        assert debts[0] == pytest.approx(25.0)

    def test_sums_every_non_special_kind_into_liquid_assets(self) -> None:
        """Kinds other than pension, credit and debt are combined into liquid assets."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        cash_id = add_item(LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        crypto_id = add_item(LOCATION, make_account(name="Wallet", kind=AccountKind.CRYPTO))
        save_balance(LOCATION, cash_id, 1, 100.0)
        save_balance(LOCATION, crypto_id, 1, 50.0)

        liquid_assets, *_ = fetch_net_worth_components(LOCATION)

        assert liquid_assets[0] == pytest.approx(150.0)

    def test_returns_all_zeros_when_no_balances_are_logged(self) -> None:
        """With nothing logged, every component is a 12-month array of zeros."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)

        components = fetch_net_worth_components(LOCATION)

        for component in components:
            assert component.shape == (12,)
            assert (component == 0).all()


class TestFetchPreviousYearEndNetWorthComponents:
    """Tests for `fetch_previous_year_end_net_worth_components`."""

    def test_returns_all_zeros_when_the_previous_year_has_no_database(self) -> None:
        """With no `year - 1` database file at all, there is nothing to report."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        assert fetch_previous_year_end_net_worth_components(LOCATION) == (0.0, 0.0, 0.0, 0.0)

    def test_returns_liquid_assets_and_pension_from_the_previous_year_s_december(self) -> None:
        """Liquid assets and the pension fund come from `year - 1`'s own December balances."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        cash_id = add_item(PRIOR_LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        pension_id = add_item(PRIOR_LOCATION, make_account(name="Pension", kind=AccountKind.PENSION))
        save_balance(PRIOR_LOCATION, cash_id, 12, 100.0)
        save_balance(PRIOR_LOCATION, pension_id, 12, 200.0)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        liquid_assets, pension, credits, debts = fetch_previous_year_end_net_worth_components(LOCATION)

        assert (liquid_assets, pension) == (100.0, 200.0)
        assert (credits, debts) == (0.0, 0.0)

    def test_ignores_months_other_than_december(self) -> None:
        """Only the December snapshot counts, not other months' balances."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        cash_id = add_item(PRIOR_LOCATION, make_account(kind=AccountKind.CASH))
        save_balance(PRIOR_LOCATION, cash_id, 6, 999.0)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        liquid_assets, *_ = fetch_previous_year_end_net_worth_components(LOCATION)

        assert liquid_assets == 0.0

    def test_returns_credits_and_debts_from_the_current_year_s_own_opening_balances(self) -> None:
        """Credits/debts come from `year`'s own accounts, never from `year - 1`'s database.

        This is what makes them consistent with the Accounts view, which shows the very same
        `opening_balance` field for a Debt/Credit account's "previous year" cell.
        """
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Owed to me", kind=AccountKind.CREDIT, opening_balance=50.0))
        add_item(LOCATION, make_account(name="Owed by me", kind=AccountKind.DEBT, opening_balance=25.0))

        _, _, credits, debts = fetch_previous_year_end_net_worth_components(LOCATION)

        assert (credits, debts) == (50.0, 25.0)

    def test_credits_and_debts_are_unaffected_by_a_missing_previous_year_database(self) -> None:
        """Unlike liquid assets/pension, credits/debts don't need `year - 1` to exist at all."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Owed by me", kind=AccountKind.DEBT, opening_balance=900.0))
        # `year - 1` deliberately has no database file

        _, _, _, debts = fetch_previous_year_end_net_worth_components(LOCATION)

        assert debts == pytest.approx(900.0)


class TestFetchOpeningBalancesByKind:
    """Tests for `fetch_opening_balances_by_kind`."""

    def test_is_empty_when_there_are_no_debt_credit_accounts(self) -> None:
        """With no Debt/Credit accounts at all, there is nothing to report."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Checking", kind=AccountKind.CASH, opening_balance=100.0))

        assert fetch_opening_balances_by_kind(LOCATION) == {}

    def test_sums_opening_balances_across_every_account_of_the_same_kind(self) -> None:
        """Two accounts of the same kind contribute to a single combined total."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT, opening_balance=100.0))
        add_item(LOCATION, make_account(name="Dad", kind=AccountKind.DEBT, opening_balance=50.0))

        assert fetch_opening_balances_by_kind(LOCATION) == {AccountKind.DEBT: 150.0}

    def test_keeps_debt_and_credit_totals_separate(self) -> None:
        """Debt and Credit accounts contribute to independent totals."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT, opening_balance=100.0))
        add_item(LOCATION, make_account(name="Alex", kind=AccountKind.CREDIT, opening_balance=40.0))

        assert fetch_opening_balances_by_kind(LOCATION) == {AccountKind.DEBT: 100.0, AccountKind.CREDIT: 40.0}


class TestSaveBalance:
    """Tests for `save_balance`."""

    def test_inserts_a_new_snapshot(self) -> None:
        """A month with no existing snapshot gets a new row."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account())

        save_balance(LOCATION, account_id, 1, 100.0)

        assert fetch_account_balances(LOCATION) == {(account_id, 1): 100.0}

    def test_updates_an_existing_snapshot_instead_of_duplicating_it(self) -> None:
        """Saving the same account/month twice updates the row rather than inserting another."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account())

        save_balance(LOCATION, account_id, 1, 100.0)
        save_balance(LOCATION, account_id, 1, 150.0)

        assert fetch_account_balances(LOCATION) == {(account_id, 1): 150.0}


class TestDeleteBalance:
    """Tests for `delete_balance`."""

    def test_removes_an_existing_snapshot(self) -> None:
        """A logged balance is gone after being deleted."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account())
        save_balance(LOCATION, account_id, 1, 100.0)

        delete_balance(LOCATION, account_id, 1)

        assert fetch_account_balances(LOCATION) == {}

    def test_is_a_harmless_no_op_for_a_nonexistent_snapshot(self) -> None:
        """Deleting a month that was never logged does not raise."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)

        delete_balance(LOCATION, 999, 1)  # must not raise


class TestDeleteAccount:
    """Tests for `delete_account`."""

    def test_deletes_the_account_and_every_balance_logged_for_it(self) -> None:
        """Deleting an account cascades to remove its balance snapshots too."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account())
        save_balance(LOCATION, account_id, 1, 100.0)
        save_balance(LOCATION, account_id, 2, 200.0)

        assert delete_account(LOCATION, account_id) is True
        assert fetch_account_balances(LOCATION) == {}
        with pytest.raises(ValueError, match="No item with id"):
            fetch_by_id(LOCATION, WhichDb.ACCOUNTS, account_id)

    def test_returns_false_for_a_nonexistent_account(self) -> None:
        """Deleting an id that doesn't exist returns `False` instead of raising."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)

        assert delete_account(LOCATION, 999) is False


class TestSeedAccountsForNewYear:
    """Tests for `seed_accounts_for_new_year`."""

    def test_is_a_no_op_when_no_prior_year_exists(self) -> None:
        """With no earlier year's database around, the current year is left untouched."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(LOCATION)

        assert fetch_account_definitions(LOCATION) == []

    def test_copies_account_names_and_kinds_from_the_most_recent_prior_year(self) -> None:
        """Accounts (but not balances) are carried over from the latest year that has any."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_account_id = add_item(PRIOR_LOCATION, make_account(name="Savings", kind=AccountKind.EMERGENCY))
        save_balance(PRIOR_LOCATION, prior_account_id, 12, 5000.0)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(LOCATION)

        copied = [account for _, account in fetch_account_definitions(LOCATION)]
        assert len(copied) == 1
        assert copied[0].name == "Savings"
        assert copied[0].kind == AccountKind.EMERGENCY

    def test_does_not_copy_balances(self) -> None:
        """Only the account definitions are seeded, never the logged balances."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_account_id = add_item(PRIOR_LOCATION, make_account())
        save_balance(PRIOR_LOCATION, prior_account_id, 1, 100.0)

        seed_accounts_for_new_year(LOCATION)

        assert fetch_account_balances(LOCATION) == {}

    def test_is_a_no_op_when_the_current_year_already_has_accounts(self) -> None:
        """Existing accounts for the current year are never duplicated from a prior year."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        add_item(PRIOR_LOCATION, make_account(name="Old"))
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Existing"))

        seed_accounts_for_new_year(LOCATION)

        names = [account.name for _, account in fetch_account_definitions(LOCATION)]
        assert names == ["Existing"]

    def test_seeds_a_debt_credit_account_s_opening_balance_from_the_prior_year_s_december(self) -> None:
        """A Debt/Credit account's opening balance carries over as the prior year's Dec balance."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        save_balance(PRIOR_LOCATION, prior_id, 12, 900.0)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(LOCATION)

        copied = dict(fetch_account_definitions(LOCATION))
        assert len(copied) == 1
        assert next(iter(copied.values())).opening_balance == pytest.approx(900.0)

    def test_does_not_set_an_opening_balance_for_non_debt_credit_accounts(self) -> None:
        """A regular account's opening balance stays 0.0 - it isn't a computed kind."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Checking", kind=AccountKind.CASH))
        save_balance(PRIOR_LOCATION, prior_id, 12, 900.0)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        seed_accounts_for_new_year(LOCATION)

        copied = dict(fetch_account_definitions(LOCATION))
        assert next(iter(copied.values())).opening_balance == 0.0


class TestFetchPreviousYearAccountIds:
    """Tests for `fetch_previous_year_account_ids`."""

    def test_is_empty_when_the_previous_year_has_no_database(self) -> None:
        """With no `year - 1` database file at all, there is nothing to match against."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        assert fetch_previous_year_account_ids(LOCATION) == {}

    def test_maps_account_names_to_their_id_in_the_previous_year(self) -> None:
        """Each account name in `year - 1` resolves to its id there."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Checking"))

        assert fetch_previous_year_account_ids(LOCATION) == {"Checking": prior_id}


class TestFetchPreviousYearEndBalances:
    """Tests for `fetch_previous_year_end_balances`."""

    def test_is_empty_when_the_previous_year_has_no_database(self) -> None:
        """With no `year - 1` database file at all, there is nothing to report."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        assert fetch_previous_year_end_balances(LOCATION) == {}

    def test_only_includes_accounts_with_a_logged_december_balance(self) -> None:
        """An account that exists in `year - 1` but has no December balance is excluded."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        logged_id = add_item(PRIOR_LOCATION, make_account(name="Checking"))
        add_item(PRIOR_LOCATION, make_account(name="Savings"))
        save_balance(PRIOR_LOCATION, logged_id, 12, 999.0)

        assert fetch_previous_year_end_balances(LOCATION) == {"Checking": 999.0}


class TestSavePreviousYearEndBalance:
    """Tests for `save_previous_year_end_balance`."""

    def test_saves_into_the_previous_year_s_database_by_matching_name(self) -> None:
        """The balance is written as month 12 of the matching account in `year - 1`."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Checking"))

        save_previous_year_end_balance(LOCATION, "Checking", AccountKind.CASH, 999.0)

        assert fetch_account_balances(PRIOR_LOCATION) == {(prior_id, 12): 999.0}

    def test_updates_an_existing_december_balance_instead_of_duplicating_it(self) -> None:
        """Saving twice updates the same row rather than inserting another."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Checking"))

        save_previous_year_end_balance(LOCATION, "Checking", AccountKind.CASH, 100.0)
        save_previous_year_end_balance(LOCATION, "Checking", AccountKind.CASH, 150.0)

        assert fetch_account_balances(PRIOR_LOCATION) == {(prior_id, 12): 150.0}

    def test_creates_the_account_when_the_previous_year_s_database_exists_but_lacks_it(self) -> None:
        """A matching account is created in `year - 1` if it isn't there yet."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)

        save_previous_year_end_balance(LOCATION, "New Account", AccountKind.CASH, 500.0)

        created = dict(fetch_account_definitions(PRIOR_LOCATION))
        assert len(created) == 1
        prior_id, account = next(iter(created.items()))
        assert account.name == "New Account"
        assert account.kind == AccountKind.CASH
        assert fetch_account_balances(PRIOR_LOCATION) == {(prior_id, 12): 500.0}

    def test_creates_the_previous_year_s_database_when_it_does_not_exist_at_all(self) -> None:
        """Logging this column never requires the previous year to have been used already."""
        save_previous_year_end_balance(LOCATION, "New Account", AccountKind.CRYPTO, 42.0)

        created = dict(fetch_account_definitions(PRIOR_LOCATION))
        assert len(created) == 1
        prior_id, account = next(iter(created.items()))
        assert account.name == "New Account"
        assert account.kind == AccountKind.CRYPTO
        assert fetch_account_balances(PRIOR_LOCATION) == {(prior_id, 12): 42.0}


class TestDeletePreviousYearEndBalance:
    """Tests for `delete_previous_year_end_balance`."""

    def test_removes_the_december_balance_in_the_previous_year(self) -> None:
        """The matching account's December balance in `year - 1` is deleted."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)
        prior_id = add_item(PRIOR_LOCATION, make_account(name="Checking"))
        save_balance(PRIOR_LOCATION, prior_id, 12, 999.0)

        delete_previous_year_end_balance(LOCATION, "Checking")

        assert fetch_account_balances(PRIOR_LOCATION) == {}

    def test_is_a_harmless_no_op_when_no_matching_account_exists(self) -> None:
        """Deleting for a name with no match in `year - 1` does not raise."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNT_BALANCES)

        delete_previous_year_end_balance(LOCATION, "Nonexistent")  # must not raise


class TestGetOrCreateDebtCreditAccount:
    """Tests for `get_or_create_debt_credit_account`."""

    def test_creates_a_new_account_when_no_match_exists(self) -> None:
        """With no existing account of that name, a new one is created and reported as such."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)

        account_id, was_created = get_or_create_debt_credit_account(LOCATION, "Mom", AccountKind.DEBT)

        assert was_created is True
        account = fetch_by_id(LOCATION, WhichDb.ACCOUNTS, account_id)
        assert account.name == "Mom"
        assert account.kind == AccountKind.DEBT

    def test_matches_an_existing_account_case_insensitively(self) -> None:
        """An existing account of the same kind is reused rather than duplicated."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        existing_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))

        account_id, was_created = get_or_create_debt_credit_account(LOCATION, "mom", AccountKind.DEBT)

        assert was_created is False
        assert account_id == existing_id
        assert len(fetch_account_definitions(LOCATION)) == 1

    def test_raises_when_an_existing_account_has_a_different_kind(self) -> None:
        """A name collision with an unrelated account of another kind is not silently reused."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.CASH))

        with pytest.raises(ValueError, match="already exists as CASH"):
            get_or_create_debt_credit_account(LOCATION, "Mom", AccountKind.DEBT)


class TestSaveAccountOpeningBalance:
    """Tests for `save_account_opening_balance`."""

    def test_sets_the_opening_balance_and_recomputes_the_account(self) -> None:
        """The new opening balance is persisted and immediately reflected in the monthly balances."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))

        save_account_opening_balance(LOCATION, account_id, 900.0)

        account = fetch_by_id(LOCATION, WhichDb.ACCOUNTS, account_id)
        assert account.opening_balance == pytest.approx(900.0)
        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(900.0)

    def test_never_touches_another_year_s_database(self) -> None:
        """Unlike the old previous-year proxy, this only ever writes to `year`'s own account row."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))

        save_account_opening_balance(LOCATION, account_id, 900.0)

        assert fetch_account_definitions(PRIOR_LOCATION) == []


class TestRecomputeAccountBalance:
    """Tests for `recompute_account_balance`."""

    def test_is_a_no_op_for_a_non_debt_credit_account(self) -> None:
        """An account of a kind other than Debt/Credit is left untouched."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        account_id = add_item(LOCATION, make_account(kind=AccountKind.CASH))

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION) == {}

    def test_debt_named_as_source_increases_the_balance(self) -> None:
        """Borrowing (the account is the transfer's source) increases a Debt balance."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=200.0, month=3))

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 3)] == pytest.approx(200.0)

    def test_debt_named_as_destination_decreases_the_balance(self) -> None:
        """Repaying (the account is the transfer's destination) decreases a Debt balance."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source=None, destination="Mom", amount=50.0, month=1))

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(-50.0)

    def test_credit_named_as_source_decreases_the_balance(self) -> None:
        """Being repaid (the account is the transfer's source) decreases a Credit balance."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Alex", kind=AccountKind.CREDIT))
        add_item(
            LOCATION, make_transfer(kind=SYSTEM_KIND_CREDIT, source="Alex", destination=None, amount=30.0, month=1)
        )

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(-30.0)

    def test_credit_named_as_destination_increases_the_balance(self) -> None:
        """Lending more (the account is the transfer's destination) increases a Credit balance."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Alex", kind=AccountKind.CREDIT))
        add_item(
            LOCATION, make_transfer(kind=SYSTEM_KIND_CREDIT, source=None, destination="Alex", amount=75.0, month=1)
        )

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(75.0)

    def test_starts_from_the_account_s_own_opening_balance(self) -> None:
        """The running total is anchored on the account's own field, not another year's database."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT, opening_balance=500.0))

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(500.0)

    def test_defaults_to_zero_when_no_opening_balance_was_set(self) -> None:
        """A freshly created account with no opening balance set starts its run from 0.0."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))

        recompute_account_balance(LOCATION, account_id)

        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(0.0)

    def test_carries_the_running_total_forward_through_unaffected_months(self) -> None:
        """A month with no transfer keeps the same running total as the month before it."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=2))

        recompute_account_balance(LOCATION, account_id)

        balances = fetch_account_balances(LOCATION)
        assert balances[(account_id, 1)] == pytest.approx(0.0)
        assert balances[(account_id, 2)] == pytest.approx(100.0)
        assert balances[(account_id, 6)] == pytest.approx(100.0)
        assert balances[(account_id, 12)] == pytest.approx(100.0)

    def test_does_not_touch_the_previous_year_s_database(self) -> None:
        """Recomputing `year` never reads or writes the previous year's data at all."""
        initialize_db(PRIOR_LOCATION, WhichDb.ACCOUNTS)
        add_item(PRIOR_LOCATION, make_account(name="Mom", kind=AccountKind.DEBT, opening_balance=999.0))
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))

        recompute_account_balance(LOCATION, account_id)

        prior_account = fetch_by_id(PRIOR_LOCATION, WhichDb.ACCOUNTS, 1)
        assert prior_account.opening_balance == pytest.approx(999.0)
        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(0.0)

    def test_cascades_the_recomputed_december_balance_into_the_next_year(self) -> None:
        """A matching account in `year + 1` has its opening balance and balances refreshed too."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=12))
        next_location = DbLocation(YEAR + 1)
        initialize_db(next_location, WhichDb.ACCOUNTS)
        initialize_db(next_location, WhichDb.ACCOUNT_BALANCES)
        initialize_db(next_location, WhichDb.TRANSFERS)
        next_account_id = add_item(next_location, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(
            next_location, make_transfer(kind=SYSTEM_KIND_DEBT, source=None, destination="Mom", amount=20.0, month=1)
        )

        recompute_account_balance(LOCATION, account_id)

        next_account = fetch_by_id(next_location, WhichDb.ACCOUNTS, next_account_id)
        assert next_account.opening_balance == pytest.approx(100.0)
        assert fetch_account_balances(next_location)[(next_account_id, 1)] == pytest.approx(80.0)

    def test_does_not_cascade_when_the_next_year_has_no_matching_account(self) -> None:
        """A next year with no account of that name is left untouched."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        account_id = add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=12))
        next_location = DbLocation(YEAR + 1)
        initialize_db(next_location, WhichDb.ACCOUNTS)

        recompute_account_balance(LOCATION, account_id)  # must not raise

        assert fetch_account_definitions(next_location) == []


class TestSyncTransferAccounts:
    """Tests for `sync_transfer_accounts`."""

    def test_is_a_no_op_for_a_non_debt_credit_kind(self) -> None:
        """A transfer with an unrelated kind (e.g. "Loan") never creates any account."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        transfer = make_transfer(kind="Loan", source="Mom")

        assert sync_transfer_accounts(LOCATION, transfer) == []
        assert fetch_account_definitions(LOCATION) == []

    def test_creates_and_recomputes_the_account_named_in_source(self) -> None:
        """A Debt transfer naming a new account in `source` creates and populates it."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        transfer = make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0)
        add_item(LOCATION, transfer)

        sync_transfer_accounts(LOCATION, transfer)

        accounts = dict(fetch_account_definitions(LOCATION))
        assert len(accounts) == 1
        account_id, account = next(iter(accounts.items()))
        assert account.name == "Mom"
        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(100.0)

    def test_creates_and_recomputes_accounts_for_both_source_and_destination(self) -> None:
        """A transfer naming an account on both sides syncs both of them."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        transfer = make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination="Dad", amount=100.0)
        add_item(LOCATION, transfer)

        sync_transfer_accounts(LOCATION, transfer)

        names = {account.name for _, account in fetch_account_definitions(LOCATION)}
        assert names == {"Mom", "Dad"}

    def test_reports_only_newly_created_account_names(self) -> None:
        """An account that already existed is not reported, even though it's still recomputed."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT))
        transfer = make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination="Dad", amount=100.0)
        add_item(LOCATION, transfer)

        assert sync_transfer_accounts(LOCATION, transfer) == ["Dad"]

    def test_propagates_the_kind_mismatch_error(self) -> None:
        """A name collision with an unrelated account of another kind is surfaced, not swallowed."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.ACCOUNT_BALANCES)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.CASH))
        transfer = make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None)
        add_item(LOCATION, transfer)

        with pytest.raises(ValueError, match="already exists as CASH"):
            sync_transfer_accounts(LOCATION, transfer)


class TestRecomputeAllDebtCreditBalances:
    """Tests for `recompute_all_debt_credit_balances`."""

    def test_backfills_accounts_from_existing_unlinked_transfers(self) -> None:
        """Historical Debt/Credit transfers, never synced before, get their accounts built."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=1))
        add_item(
            LOCATION,
            make_transfer(kind=SYSTEM_KIND_CREDIT, source=None, destination="Alex", amount=40.0, month=2),
        )

        recompute_all_debt_credit_balances()

        accounts = {account.name: (account_id, account) for account_id, account in fetch_account_definitions(LOCATION)}
        assert accounts["Mom"][1].kind == AccountKind.DEBT
        assert accounts["Alex"][1].kind == AccountKind.CREDIT
        balances = fetch_account_balances(LOCATION)
        assert balances[(accounts["Mom"][0], 1)] == pytest.approx(100.0)
        assert balances[(accounts["Alex"][0], 2)] == pytest.approx(40.0)

    def test_is_idempotent(self) -> None:
        """Running it twice does not duplicate accounts or change the computed balances."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=1))

        recompute_all_debt_credit_balances()
        recompute_all_debt_credit_balances()

        accounts = fetch_account_definitions(LOCATION)
        assert len(accounts) == 1
        account_id, _ = accounts[0]
        assert fetch_account_balances(LOCATION)[(account_id, 1)] == pytest.approx(100.0)

    def test_reports_years_profiles_and_names_of_newly_created_accounts(self) -> None:
        """A brand new account is flagged, since its opening balance defaults to 0.0."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=1))

        created = recompute_all_debt_credit_balances()

        assert created == [(YEAR, DEFAULT_PROFILE_NAME, "Mom")]

    def test_does_not_flag_an_account_that_already_existed(self) -> None:
        """An account that already existed before the run is not reported, even if recomputed."""
        initialize_db(LOCATION, WhichDb.ACCOUNTS)
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_account(name="Mom", kind=AccountKind.DEBT, opening_balance=300.0))
        add_item(LOCATION, make_transfer(kind=SYSTEM_KIND_DEBT, source="Mom", destination=None, amount=100.0, month=1))

        created = recompute_all_debt_credit_balances()

        assert created == []
