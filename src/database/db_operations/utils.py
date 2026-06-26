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
