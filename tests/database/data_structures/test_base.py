"""Unit tests for the `:class:DataContainer` class."""

from database.data_structures.expense import Categories, Expense
from database.data_structures.income import Income, Sources


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
