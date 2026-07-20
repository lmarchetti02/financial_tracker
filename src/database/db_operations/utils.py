from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field

from flet import DataCell

type RowGenerator = Generator[tuple[int, list[DataCell]], None, None]


@dataclass
class SortingConfig(ABC):
    """Helper class to properly sort columns.

    Attributes:
        col_id (int): The ID of the column given by flet.
        ascending (int): Whether the column is to be sorted in ascending
            (`True`) or descending (`False`) order.
        sql_command (str): The sqlite command that corresponds to the given
            `col_id` and `ascending`.

    Raises:
        ValueError: If the column is not sortable.
    """

    col_id: int
    ascending: bool

    sql_command: str = field(init=False)

    @abstractmethod
    def __post_init__(self) -> None:
        """Converts the attributes given by flet to strings that can be passed to sqlite."""

    def _resolve(self, columns: dict[int, str]) -> None:
        """Sets `sql_command` from a `col_id`-to-column(s) mapping.

        Args:
            columns (dict[int, str]): Maps a sortable `col_id` to the SQL column name(s) to order
                by for that column (comma-separated if more than one).

        Raises:
            ValueError: If `col_id` is not in `columns`.
        """
        if self.col_id not in columns:
            raise ValueError("You cannot sort this column.")

        order = "ASC" if self.ascending else "DESC"
        cols = [c.strip() for c in columns[self.col_id].split(",")]
        self.sql_command = ", ".join(f"{c} {order}" for c in cols)
