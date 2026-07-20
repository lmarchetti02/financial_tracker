"""Unit tests for `database.db_operations.generic`."""

import sqlite3 as sq

import pytest

from database.data_structures.expense import Categories, Expense
from database.data_structures.income import Income, Sources
from database.data_structures.transfer import Kind, Transfer
from database.db_operations.generic import (
    WhichDb,
    add_item,
    edit_item,
    fetch_by_id,
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
        [(WhichDb.EXPENSES, "idx_category"), (WhichDb.INCOMES, "idx_source"), (WhichDb.TRANSFERS, "idx_kind")],
    )
    def test_creates_the_domain_specific_index(self, db: WhichDb, index_name: str) -> None:
        """Each DB kind gets its own extra index (category/source/kind)."""
        initialize_db(YEAR, db)

        with sq.connect(get_db_path(YEAR)) as connection:
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}

        assert index_name in indexes


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
