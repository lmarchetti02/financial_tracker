"""Unit tests for `database.db_operations.utils`."""

import pytest

from database.db_operations.utils import SortingConfig


class TestSortingConfig:
    """Tests for `SortingConfig`."""

    def test_cannot_be_instantiated_directly(self) -> None:
        """`SortingConfig` is abstract; only its concrete per-domain subclasses are usable."""
        with pytest.raises(TypeError):
            SortingConfig(col_id=0, ascending=True)
