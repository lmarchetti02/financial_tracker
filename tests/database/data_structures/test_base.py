"""Unit tests for the `:class:DataContainer` class."""

import sqlite3 as sq

from database.data_structures.expense import Categories, Expense
from database.data_structures.income import Income, Sources
from database.data_structures.transfer import Transfer


def make_expense(**overrides: object) -> Expense:
    """Builds an `:class:Expense` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 6,
        "day_start": 10,
        "day_end": None,
        "description": "groceries",
        "category": Categories.FOOD_AND_DRINKS,
        "cost": 25.5,
    }
    defaults.update(overrides)
    return Expense(**defaults)


class TestCreateTable:
    """Tests for `DataContainer.create_table`."""

    def test_includes_an_autoincrement_primary_key(self) -> None:
        """The generated statement always adds an autoincrement `id` primary key."""
        assert "id INTEGER PRIMARY KEY AUTOINCREMENT" in Expense.create_table()

    def test_uses_the_subclasses_table_name(self) -> None:
        """The statement targets the subclass's own `db_name`."""
        assert f"CREATE TABLE IF NOT EXISTS {Expense.db_name}" in Expense.create_table()

    def test_maps_python_types_to_sqlite_types(self) -> None:
        """`int`/`float`/`str`/enum fields map to `INTEGER`/`REAL`/`TEXT`/`TEXT` respectively."""
        cmd = Expense.create_table()

        assert "month INTEGER NOT NULL" in cmd
        assert "cost REAL NOT NULL" in cmd
        assert "description TEXT NOT NULL" in cmd
        assert "category TEXT NOT NULL" in cmd

    def test_marks_optional_fields_as_nullable(self) -> None:
        """A `X | None` field is emitted without a `NOT NULL` constraint."""
        cmd = Expense.create_table()

        assert "day_end INTEGER" in cmd
        assert "day_end INTEGER NOT NULL" not in cmd


class TestAddMissingColumns:
    """Tests for `DataContainer.add_missing_columns`."""

    def _legacy_transfers_table(self, cursor: sq.Cursor) -> None:
        """Creates a `transfers` table using the schema that predates `day`/`fee`/`fee_expense_id`."""
        cursor.execute(
            "CREATE TABLE transfers ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "month INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "
            "description TEXT NOT NULL, "
            "source TEXT, "
            "destination TEXT, "
            "amount REAL NOT NULL)"
        )
        cursor.execute(
            "INSERT INTO transfers (month, kind, description, source, destination, amount) "
            "VALUES (3, 'LOAN', 'legacy transfer', 'Bank A', NULL, 50.0)"
        )

    def test_adds_columns_missing_from_an_existing_table(self) -> None:
        """Fields present on the dataclass but absent from the table are added."""
        with sq.connect(":memory:") as connection:
            cursor = connection.cursor()
            self._legacy_transfers_table(cursor)

            Transfer.add_missing_columns(cursor)

            columns = {row[1] for row in cursor.execute("PRAGMA table_info(transfers)")}

        assert {"day", "fee", "fee_expense_id"} <= columns

    def test_is_idempotent(self) -> None:
        """Calling it again once the columns already exist does not raise."""
        with sq.connect(":memory:") as connection:
            cursor = connection.cursor()
            self._legacy_transfers_table(cursor)

            Transfer.add_missing_columns(cursor)
            Transfer.add_missing_columns(cursor)  # must not raise

    def test_backfills_a_not_null_column_with_its_dataclass_default(self) -> None:
        """A `NOT NULL` column added via migration is backfilled so existing rows stay valid."""
        with sq.connect(":memory:") as connection:
            connection.row_factory = sq.Row
            cursor = connection.cursor()
            self._legacy_transfers_table(cursor)

            Transfer.add_missing_columns(cursor)

            row = cursor.execute("SELECT * FROM transfers WHERE id = 1").fetchone()

        transfer = Transfer.init_from_tuple(tuple(row)[1:])
        assert transfer.day == 1
        assert transfer.fee is None
        assert transfer.fee_expense_id is None


class TestInitFromTuple:
    """Tests for `DataContainer.init_from_tuple`."""

    def test_reconstructs_an_equivalent_instance(self) -> None:
        """A row tuple built from an instance's own fields round-trips back to an equal instance."""
        expense = make_expense()
        row = (
            expense.month,
            expense.day_start,
            expense.day_end,
            expense.description,
            expense.category.name,
            expense.cost,
        )

        assert Expense.init_from_tuple(row) == expense

    def test_restores_enum_fields_by_name(self) -> None:
        """An enum field stored as its `.name` is reconstructed back into the enum member."""
        income = Income(month=1, source=Sources.INVESTMENTS, description="dividends", amount=50.0)
        row = (income.month, income.source.name, income.description, income.amount)

        reconstructed = Income.init_from_tuple(row)

        assert reconstructed.source is Sources.INVESTMENTS


class TestMonthColumn:
    """Tests for `DataContainer.month_column`."""

    def test_is_a_fixed_width_numeric_column(self) -> None:
        """The shared month column is numeric and has a fixed width, regardless of the subclass."""
        column = Expense.month_column()

        assert column.numeric is True
        assert column.fixed_width == 80


class TestMonthCell:
    """Tests for `DataContainer.month_cell`."""

    def test_renders_the_row_s_month(self) -> None:
        """The cell displays the row's `month` value as text."""
        cell = Expense.month_cell({"month": 6})

        assert cell.content.content.value == "6"


class TestSub:
    """Tests for `DataContainer.__sub__`."""

    def test_only_includes_changed_fields(self) -> None:
        """Fields with equal values on both sides are omitted from the diff."""
        original = make_expense(cost=10.0, description="old")
        updated = make_expense(cost=20.0, description="old")

        assert (original - updated) == {"cost": 20.0}

    def test_stores_enum_differences_by_name(self) -> None:
        """A changed enum field is stored in the diff as its `.name`, not the member itself."""
        original = make_expense(category=Categories.FOOD_AND_DRINKS)
        updated = make_expense(category=Categories.TRAVEL)

        assert (original - updated) == {"category": "TRAVEL"}

    def test_returns_empty_dict_for_identical_instances(self) -> None:
        """Two field-for-field identical instances diff to an empty dict."""
        assert (make_expense() - make_expense()) == {}
