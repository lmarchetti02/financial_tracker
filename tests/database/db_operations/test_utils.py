"""Unit tests for `database.db_operations.utils`."""

from dataclasses import dataclass

import pytest

from database.db_operations.utils import SortingConfig


@dataclass
class _ConcreteSortingConfig(SortingConfig):
    """Minimal concrete subclass used to exercise `SortingConfig._resolve`."""

    def __post_init__(self) -> None:  # noqa: D105
        self._resolve({0: "foo", 1: "bar, baz"})


class TestSortingConfig:
    """Tests for `SortingConfig`."""

    def test_cannot_be_instantiated_directly(self) -> None:
        """`SortingConfig` is abstract; only its concrete per-domain subclasses are usable."""
        with pytest.raises(TypeError):
            SortingConfig(col_id=0, ascending=True)


class TestResolve:
    """Tests for `SortingConfig._resolve`."""

    def test_ascending_maps_to_asc(self) -> None:
        """`ascending=True` produces an `ASC` order suffix."""
        config = _ConcreteSortingConfig(col_id=0, ascending=True)

        assert config.sql_command == "foo ASC"

    def test_descending_maps_to_desc(self) -> None:
        """`ascending=False` produces a `DESC` order suffix."""
        config = _ConcreteSortingConfig(col_id=0, ascending=False)

        assert config.sql_command == "foo DESC"

    def test_multiple_columns_each_get_the_order_suffix(self) -> None:
        """A comma-separated column mapping orders by every column with the same suffix."""
        config = _ConcreteSortingConfig(col_id=1, ascending=True)

        assert config.sql_command == "bar ASC, baz ASC"

    def test_unmapped_col_id_raises_value_error(self) -> None:
        """An unmapped `col_id` raises a clear `ValueError`."""
        with pytest.raises(ValueError, match="You cannot sort this column."):
            _ConcreteSortingConfig(col_id=99, ascending=True)
