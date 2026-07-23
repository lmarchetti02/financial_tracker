"""Unit tests for `database.db_operations.config`."""

import pytest

from database.data_structures.expense import Expense
from database.db_operations.config import (
    LookupKind,
    add_lookup_option,
    delete_lookup_option,
    fetch_categories,
    fetch_kinds,
    fetch_lookup_options,
    fetch_sources,
    get_config_db_path,
    get_theme_preference,
    initialize_config_db,
    is_lookup_option_in_use,
    rename_lookup_option,
    set_theme_preference,
)
from database.db_operations.generic import WhichDb, add_item, fetch_by_id, initialize_db

YEAR = 2024


def make_expense(**overrides: object) -> Expense:
    """Builds an `:class:Expense` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "day_start": 1,
        "description": "test expense",
        "category": "Food and drinks",
        "cost": 10.0,
    }
    defaults.update(overrides)
    return Expense(**defaults)


class TestGetConfigDbPath:
    """Tests for `get_config_db_path`."""

    def test_path_is_not_tied_to_any_year(self) -> None:
        """Unlike `get_db_path`, the config file has a fixed name."""
        assert get_config_db_path().name == "config.db"


class TestInitializeConfigDb:
    """Tests for `initialize_config_db`."""

    def test_seeds_categories_with_the_default_entries(self) -> None:
        """The `categories` table is seeded, including the system-reserved trading-fee entry."""
        initialize_config_db()

        options = fetch_lookup_options(LookupKind.CATEGORIES)

        names = {o.name for o in options}
        assert "Food and drinks" in names
        assert any(o.name == "Trading fee" and o.is_system for o in options)

    def test_seeds_sources_with_the_default_entries(self) -> None:
        """The `sources` table is seeded, including the system-reserved investments entry."""
        initialize_config_db()

        options = fetch_lookup_options(LookupKind.SOURCES)

        names = {o.name for o in options}
        assert "Salary" in names
        assert any(o.name == "Investments" and o.is_system for o in options)

    def test_seeds_kinds_with_the_default_entries(self) -> None:
        """The `kinds` table is seeded, including the system-reserved investment entry."""
        initialize_config_db()

        options = fetch_lookup_options(LookupKind.KINDS)

        names = {o.name for o in options}
        assert "Loan" in names
        assert any(o.name == "Investment" and o.is_system for o in options)

    def test_is_idempotent(self) -> None:
        """Calling it twice does not raise or duplicate the seeded entries."""
        initialize_config_db()
        initialize_config_db()

        options = fetch_lookup_options(LookupKind.CATEGORIES)

        assert len([o for o in options if o.name == "Food and drinks"]) == 1

    def test_migrates_legacy_names_in_existing_yearly_databases(self) -> None:
        """A row written before this table existed (storing the old enum member name) is rewritten."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category="FOOD_AND_DRINKS"))

        initialize_config_db()

        expense = fetch_by_id(YEAR, WhichDb.EXPENSES, 1)
        assert expense.category == "Food and drinks"


class TestFetchLookupOptions:
    """Tests for `fetch_lookup_options`."""

    def test_returns_entries_sorted_alphabetically(self) -> None:
        """Entries come back ordered by name."""
        initialize_config_db()

        names = [o.name for o in fetch_lookup_options(LookupKind.KINDS)]

        assert names == sorted(names)


class TestFetchCategories:
    """Tests for `fetch_categories`."""

    def test_returns_the_seeded_category_names(self) -> None:
        """The default categories are present as plain strings."""
        initialize_config_db()

        assert "Food and drinks" in fetch_categories()


class TestFetchSources:
    """Tests for `fetch_sources`."""

    def test_returns_the_seeded_source_names(self) -> None:
        """The default sources are present as plain strings."""
        initialize_config_db()

        assert "Salary" in fetch_sources()


class TestFetchKinds:
    """Tests for `fetch_kinds`."""

    def test_returns_the_seeded_kind_names(self) -> None:
        """The default kinds are present as plain strings."""
        initialize_config_db()

        assert "Loan" in fetch_kinds()


class TestAddLookupOption:
    """Tests for `add_lookup_option`."""

    def test_adds_a_new_entry(self) -> None:
        """A new, non-system entry is appended to the lookup list."""
        initialize_config_db()

        add_lookup_option(LookupKind.CATEGORIES, "Gifts for pets")

        assert "Gifts for pets" in fetch_categories()

    def test_rejects_a_blank_name(self) -> None:
        """A blank (or whitespace-only) name is rejected."""
        initialize_config_db()

        with pytest.raises(ValueError, match="blank"):
            add_lookup_option(LookupKind.CATEGORIES, "   ")

    def test_rejects_a_duplicate_name_case_insensitively(self) -> None:
        """An entry with the same name, regardless of case, is rejected."""
        initialize_config_db()

        with pytest.raises(ValueError, match="already exists"):
            add_lookup_option(LookupKind.CATEGORIES, "food and drinks")


class TestRenameLookupOption:
    """Tests for `rename_lookup_option`."""

    def test_renames_the_entry(self) -> None:
        """The entry's name is updated in the lookup list."""
        initialize_config_db()

        rename_lookup_option(LookupKind.CATEGORIES, "Presents", "Gifts")

        names = fetch_categories()
        assert "Gifts" in names
        assert "Presents" not in names

    def test_cascades_the_rename_to_every_yearly_database(self) -> None:
        """Existing rows referencing the old name are updated to the new one."""
        initialize_config_db()
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category="Presents"))

        rename_lookup_option(LookupKind.CATEGORIES, "Presents", "Gifts")

        expense = fetch_by_id(YEAR, WhichDb.EXPENSES, 1)
        assert expense.category == "Gifts"

    def test_refuses_to_rename_a_system_entry(self) -> None:
        """The trading-fee category can't be renamed, since `transfers.py` depends on its name."""
        initialize_config_db()

        with pytest.raises(ValueError, match="required by the app"):
            rename_lookup_option(LookupKind.CATEGORIES, "Trading fee", "Fees")

    def test_refuses_a_blank_new_name(self) -> None:
        """A blank new name is rejected."""
        initialize_config_db()

        with pytest.raises(ValueError, match="blank"):
            rename_lookup_option(LookupKind.CATEGORIES, "Presents", "   ")

    def test_refuses_a_duplicate_new_name(self) -> None:
        """Renaming to a name that already exists (case-insensitively) is rejected."""
        initialize_config_db()

        with pytest.raises(ValueError, match="already exists"):
            rename_lookup_option(LookupKind.CATEGORIES, "Presents", "travel")


class TestIsLookupOptionInUse:
    """Tests for `is_lookup_option_in_use`."""

    def test_returns_true_when_a_yearly_database_references_the_name(self) -> None:
        """A category referenced by at least one expense row is reported as in use."""
        initialize_config_db()
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category="Travel"))

        assert is_lookup_option_in_use(LookupKind.CATEGORIES, "Travel") is True

    def test_returns_false_when_no_yearly_database_references_the_name(self) -> None:
        """A category with no matching rows anywhere is reported as not in use."""
        initialize_config_db()
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category="Travel"))

        assert is_lookup_option_in_use(LookupKind.CATEGORIES, "Education") is False


class TestDeleteLookupOption:
    """Tests for `delete_lookup_option`."""

    def test_deletes_an_unused_entry(self) -> None:
        """An entry with no referencing rows anywhere is deleted, returning `True`."""
        initialize_config_db()

        assert delete_lookup_option(LookupKind.CATEGORIES, "Presents") is True
        assert "Presents" not in fetch_categories()

    def test_refuses_to_delete_a_system_entry(self) -> None:
        """The trading-fee category can't be deleted, returning `False` without touching it."""
        initialize_config_db()

        assert delete_lookup_option(LookupKind.CATEGORIES, "Trading fee") is False
        assert "Trading fee" in fetch_categories()

    def test_refuses_to_delete_an_entry_still_in_use(self) -> None:
        """A category still referenced by an expense row is not deleted, returning `False`."""
        initialize_config_db()
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(category="Travel"))

        assert delete_lookup_option(LookupKind.CATEGORIES, "Travel") is False
        assert "Travel" in fetch_categories()


class TestThemePreference:
    """Tests for `get_theme_preference`/`set_theme_preference`."""

    def test_defaults_to_light_when_unset(self) -> None:
        """Before any preference is saved, the theme defaults to light."""
        initialize_config_db()

        assert get_theme_preference() == "light"

    def test_persists_and_returns_the_set_value(self) -> None:
        """A saved preference round-trips back through `get_theme_preference`."""
        initialize_config_db()

        set_theme_preference("dark")

        assert get_theme_preference() == "dark"

    def test_overwrites_a_previously_set_value(self) -> None:
        """Setting the preference again replaces the previous value rather than erroring."""
        initialize_config_db()

        set_theme_preference("dark")
        set_theme_preference("light")

        assert get_theme_preference() == "light"
