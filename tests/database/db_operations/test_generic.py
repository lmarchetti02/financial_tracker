"""Unit tests for `database.db_operations.generic`."""

import sqlite3 as sq
from types import SimpleNamespace

import pytest

from _helpers.constants import EXPENSES_DB_NAME
from database.data_structures.expense import Categories, Expense
from database.data_structures.income import Income, Sources
from database.data_structures.transfer import Kind, Transfer
from database.db_operations.generic import (
    WhichDb,
    add_item,
    edit_item,
    fetch_by_id,
    fetch_monthly_totals,
    fetch_rows,
    get_db_path,
    initialize_db,
    remove_item,
)

YEAR = 2024


def make_expense(**overrides: object) -> Expense:
    """Builds an `:class:Expense` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "day_start": 1,
        "description": "test expense",
        "category": Categories.FOOD_AND_DRINKS,
        "cost": 10.0,
    }
    defaults.update(overrides)
    return Expense(**defaults)


def make_income(**overrides: object) -> Income:
    """Builds an `:class:Income` with sensible defaults, overridden by `overrides`."""
    defaults = {"month": 1, "source": Sources.SALARY, "description": "test income", "amount": 100.0}
    defaults.update(overrides)
    return Income(**defaults)


class TestGetDbPath:
    """Tests for `get_db_path`."""

    def test_path_is_named_after_the_year(self) -> None:
        """The DB file name embeds the requested year."""
        assert get_db_path(YEAR).name == f"{YEAR}_data.db"

    def test_different_years_map_to_different_files(self) -> None:
        """Two distinct years resolve to two distinct DB files."""
        assert get_db_path(2024) != get_db_path(2025)


class TestFetchRows:
    """Tests for `fetch_rows`."""

    def test_yields_the_id_and_row_of_every_item(self) -> None:
        """With no filter or sort, every row in the table is yielded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(description="first"))
        add_item(YEAR, make_expense(description="second"))

        ids = [row_id for row_id, _ in fetch_rows(YEAR, EXPENSES_DB_NAME, Expense)]

        assert ids == [1, 2]

    def test_filters_by_month(self) -> None:
        """Only rows matching the given month are yielded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1))
        add_item(YEAR, make_expense(month=2))

        results = list(fetch_rows(YEAR, EXPENSES_DB_NAME, Expense, month=2))

        assert [row_id for row_id, _ in results] == [2]

    def test_filters_by_extra_filter(self) -> None:
        """`extra_filter` restricts rows to those matching the given column/enum-member pair."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category=Categories.FOOD_AND_DRINKS))
        add_item(YEAR, make_expense(category=Categories.TRAVEL))

        results = list(fetch_rows(YEAR, EXPENSES_DB_NAME, Expense, extra_filter=("category", Categories.TRAVEL)))

        assert [row_id for row_id, _ in results] == [2]

    def test_sorts_according_to_the_given_sort_config(self) -> None:
        """Rows are ordered per `sort.sql_command`."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(cost=30.0))
        add_item(YEAR, make_expense(cost=10.0))
        sort = SimpleNamespace(sql_command="cost ASC")

        ids = [row_id for row_id, _ in fetch_rows(YEAR, EXPENSES_DB_NAME, Expense, sort=sort)]

        assert ids == [2, 1]


class TestFetchMonthlyTotals:
    """Tests for `fetch_monthly_totals`."""

    def test_sums_the_column_per_month_for_the_given_filter(self) -> None:
        """Values for the requested filter are summed per month; other values are excluded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1, category=Categories.FOOD_AND_DRINKS, cost=10.0))
        add_item(YEAR, make_expense(month=1, category=Categories.FOOD_AND_DRINKS, cost=5.0))
        add_item(YEAR, make_expense(month=3, category=Categories.FOOD_AND_DRINKS, cost=7.0))
        add_item(YEAR, make_expense(month=1, category=Categories.TRAVEL, cost=100.0))

        totals = fetch_monthly_totals(YEAR, EXPENSES_DB_NAME, "cost", "category", Categories.FOOD_AND_DRINKS)

        assert totals[0] == pytest.approx(15.0)
        assert totals[1] == pytest.approx(0.0)
        assert totals[2] == pytest.approx(7.0)

    def test_sums_the_column_across_all_values_when_no_filter_is_given(self) -> None:
        """Omitting `filter_column`/`filter_value` sums the column across every row."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1, category=Categories.FOOD_AND_DRINKS, cost=10.0))
        add_item(YEAR, make_expense(month=1, category=Categories.TRAVEL, cost=5.0))
        add_item(YEAR, make_expense(month=3, category=Categories.TRAVEL, cost=7.0))

        totals = fetch_monthly_totals(YEAR, EXPENSES_DB_NAME, "cost")

        assert totals[0] == pytest.approx(15.0)
        assert totals[1] == pytest.approx(0.0)
        assert totals[2] == pytest.approx(7.0)


class TestInitializeDb:
    """Tests for `initialize_db`."""

    def test_creates_a_table_for_each_db_kind(self) -> None:
        """Initializing every `:enum:WhichDb` member creates all three tables in the shared file."""
        for db in WhichDb:
            initialize_db(YEAR, db)

        with sq.connect(get_db_path(YEAR)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        assert {"expenses", "income", "transfers"} <= tables

    def test_is_idempotent(self) -> None:
        """Calling `initialize_db` twice for the same DB does not raise."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        initialize_db(YEAR, WhichDb.EXPENSES)  # must not raise

    def test_creates_a_month_index(self) -> None:
        """Every DB kind gets an index on its `month` column."""
        initialize_db(YEAR, WhichDb.EXPENSES)

        with sq.connect(get_db_path(YEAR)) as connection:
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}

        assert "idx_month" in indexes

    @pytest.mark.parametrize(
        ("db", "index_name"),
        [
            (WhichDb.EXPENSES, "idx_category"),
            (WhichDb.INCOMES, "idx_source"),
            (WhichDb.TRANSFERS, "idx_kind"),
            (WhichDb.ACCOUNT_BALANCES, "idx_account_id"),
        ],
    )
    def test_creates_the_domain_specific_index(self, db: WhichDb, index_name: str) -> None:
        """Each DB kind gets its own extra index (category/source/kind/account_id)."""
        initialize_db(YEAR, db)

        with sq.connect(get_db_path(YEAR)) as connection:
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}

        assert index_name in indexes

    def test_does_not_create_a_month_index_for_accounts(self) -> None:
        """`Account` has no `month` column, so it must not get an `idx_month`."""
        initialize_db(YEAR, WhichDb.ACCOUNTS)

        with sq.connect(get_db_path(YEAR)) as connection:
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}

        assert "idx_month" not in indexes

    def test_backfills_columns_missing_from_an_already_existing_table(self) -> None:
        """A `transfers` table created before `day`/`fee`/`fee_expense_id` existed gets them added."""
        with sq.connect(get_db_path(YEAR)) as connection:
            connection.execute(
                "CREATE TABLE transfers ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "month INTEGER NOT NULL, "
                "kind TEXT NOT NULL, "
                "description TEXT NOT NULL, "
                "source TEXT, "
                "destination TEXT, "
                "amount REAL NOT NULL)"
            )
            connection.execute(
                "INSERT INTO transfers (month, kind, description, source, destination, amount) "
                "VALUES (3, 'LOAN', 'legacy transfer', 'Bank A', NULL, 50.0)"
            )

        initialize_db(YEAR, WhichDb.TRANSFERS)

        transfer = fetch_by_id(YEAR, WhichDb.TRANSFERS, 1)
        assert transfer.day == 1
        assert transfer.fee is None
        assert transfer.fee_expense_id is None


class TestAddItem:
    """Tests for `add_item`."""

    def test_inserts_a_row_that_can_be_fetched_back(self) -> None:
        """A newly added item is retrievable via `fetch_by_id` afterwards."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        expense = make_expense(cost=42.0)

        add_item(YEAR, expense)

        assert fetch_by_id(YEAR, WhichDb.EXPENSES, 1) == expense

    def test_persists_enum_fields_by_name(self) -> None:
        """An enum field is stored as its `.name`, not its numeric value."""
        initialize_db(YEAR, WhichDb.INCOMES)
        add_item(YEAR, make_income(source=Sources.INVESTMENTS))

        with sq.connect(get_db_path(YEAR)) as connection:
            row = connection.execute("SELECT source FROM income WHERE id = 1").fetchone()

        assert row[0] == "INVESTMENTS"

    def test_rejects_an_unsupported_item_type(self) -> None:
        """An item whose type isn't a registered `:class:DataContainer` subclass is rejected."""
        with pytest.raises(ValueError, match="Unsupported item type"):
            add_item(YEAR, "not a data container")


class TestFetchById:
    """Tests for `fetch_by_id`."""

    def test_reconstructs_the_stored_object(self) -> None:
        """The fetched object is equal to the one that was originally added."""
        initialize_db(YEAR, WhichDb.TRANSFERS)
        transfer = Transfer(month=3, kind=Kind.LOAN, description="loan", source="Bank A", amount=50.0)

        add_item(YEAR, transfer)

        assert fetch_by_id(YEAR, WhichDb.TRANSFERS, 1) == transfer

    def test_unknown_id_raises_value_error(self) -> None:
        """A missing row raises a clear `ValueError` rather than crashing on an internal `None`."""
        initialize_db(YEAR, WhichDb.EXPENSES)

        with pytest.raises(ValueError, match="No item with id"):
            fetch_by_id(YEAR, WhichDb.EXPENSES, 999)


class TestRemoveItem:
    """Tests for `remove_item`."""

    def test_removes_an_existing_row(self) -> None:
        """A successful removal returns `True` and the row is no longer fetchable."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense())

        assert remove_item(YEAR, WhichDb.EXPENSES, 1) is True
        with pytest.raises(ValueError, match="No item with id"):
            fetch_by_id(YEAR, WhichDb.EXPENSES, 1)

    def test_returns_false_for_a_nonexistent_row(self) -> None:
        """Removing an ID that doesn't exist returns `False` instead of raising."""
        initialize_db(YEAR, WhichDb.EXPENSES)

        assert remove_item(YEAR, WhichDb.EXPENSES, 999) is False


class TestEditItem:
    """Tests for `edit_item`."""

    def test_updates_only_the_changed_fields(self) -> None:
        """Only the fields that differ between `old` and `new` are written to the row."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        original = make_expense(cost=10.0, description="old")
        add_item(YEAR, original)
        updated = make_expense(cost=20.0, description="old")

        assert edit_item(YEAR, 1, original, updated) is True
        assert fetch_by_id(YEAR, WhichDb.EXPENSES, 1) == updated

    def test_rejects_mismatched_types(self) -> None:
        """`old` and `new` must be instances of the same `:class:DataContainer` subclass."""
        with pytest.raises(ValueError, match="same type"):
            edit_item(YEAR, 1, make_expense(), make_income())

    def test_rejects_an_unsupported_item_type(self) -> None:
        """An item type that isn't a registered `:class:DataContainer` subclass is rejected."""
        with pytest.raises(ValueError, match="Unsupported item type"):
            edit_item(YEAR, 1, "a", "a")

    def test_a_no_op_edit_is_a_harmless_no_op(self) -> None:
        """When `old` and `new` are identical, `edit_item` returns `True` without touching the row."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        expense = make_expense()
        add_item(YEAR, expense)

        assert edit_item(YEAR, 1, expense, make_expense()) is True
        assert fetch_by_id(YEAR, WhichDb.EXPENSES, 1) == expense
