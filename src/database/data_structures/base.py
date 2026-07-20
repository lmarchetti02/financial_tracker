"""Implementation of the `:class:DataContainer` class."""

from abc import ABC, abstractmethod
from dataclasses import MISSING, fields
from enum import Enum
from logging import getLogger
from sqlite3 import Cursor, Row
from types import UnionType
from typing import ClassVar, Self, get_args, get_origin, get_type_hints

from flet import DataCell
from flet_datatable2 import DataColumn2
from pydantic.dataclasses import dataclass
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

logger = getLogger("financial_tracker")


def _convert_types(t: type) -> str:
    """Converts types from Python to Sqlite."""
    # verify "| None"
    is_optional = False

    if get_origin(t) is UnionType:
        args = get_args(t)
        if type(None) in args:
            is_optional = True
            t = next(a for a in args if a is not type(None))

    # build sqlite string
    sqlite_str = []
    if t is int:
        sqlite_str.append("INTEGER")
    elif t is float:
        sqlite_str.append("REAL")
    else:
        sqlite_str.append("TEXT")

    if not is_optional:
        sqlite_str.append("NOT NULL")

    return " ".join(sqlite_str)


@dataclass(frozen=True, kw_only=True)
class DataContainer(ABC):
    """Class representing a generic data container used in the app."""

    db_name: ClassVar[str]

    def __sub__(self, other: Self) -> dict:
        """Subtraction operator overloading.

        Args:
            other (`:class:DataContainer`): The object to subtract.

        Returns:
            dict: A dictionary with the differences between the instance and the
                other object. In particular, only the values of `other` that
                differ from `self`.
        """
        resolved_types = get_type_hints(self)

        differences = {}
        for field in fields(self):
            field_type = resolved_types[field.name]

            v_self = getattr(self, field.name)
            v_other = getattr(other, field.name)
            if v_self != v_other:
                if isinstance(field_type, type) and issubclass(field_type, Enum):
                    differences[field.name] = v_other.name
                else:
                    differences[field.name] = v_other

        return differences

    @classmethod
    def create_table(cls) -> str:
        """Generates the sqlite command to create a table based on the attributes of the class."""
        logger.info("Called 'create_table'")

        resolved_types = get_type_hints(cls)
        cmd = [f"{f.name} {_convert_types(resolved_types[f.name])}" for f in fields(cls)]
        cmd.insert(0, "id INTEGER PRIMARY KEY AUTOINCREMENT")

        return f"CREATE TABLE IF NOT EXISTS {cls.db_name} ({', '.join(cmd)})"

    @classmethod
    def add_missing_columns(cls, cursor: Cursor) -> None:
        """Adds any dataclass fields missing from an already-existing table (schema migration).

        Args:
            cursor (Cursor): An open cursor on the connection whose table should be migrated.
        """
        logger.info("Called 'add_missing_columns'")

        existing_columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({cls.db_name})")}
        resolved_types = get_type_hints(cls)

        for f in fields(cls):
            if f.name in existing_columns:
                continue

            column_def = f"{f.name} {_convert_types(resolved_types[f.name])}"
            default = f.default.default if isinstance(f.default, FieldInfo) else f.default
            has_default = default is not MISSING and default is not PydanticUndefined
            if "NOT NULL" in column_def and has_default:
                column_def += f" DEFAULT {default}"

            cursor.execute(f"ALTER TABLE {cls.db_name} ADD COLUMN {column_def}")
            logger.debug(f"Added missing column '{f.name}' to '{cls.db_name}'.")

    @classmethod
    def init_from_tuple(cls, row: tuple) -> Self:
        """Reconstructs an instance of the class from a database row tuple."""
        logger.info("Called 'init_from_tuple'")

        resolved_types = get_type_hints(cls)
        kwargs = {}

        for field, value in zip(fields(cls), row):
            # get type
            field_type = resolved_types[field.name]
            if get_origin(field_type) is UnionType:
                args = get_args(field_type)
                field_type = next(a for a in args if a is not type(None))

            # reconstruct enums
            if isinstance(field_type, type) and issubclass(field_type, Enum):
                kwargs[field.name] = field_type[value]
            else:
                kwargs[field.name] = value

        return cls(**kwargs)

    @staticmethod
    @abstractmethod
    def get_table_row(row: Row) -> list[DataCell]:
        """Returns the flet controls that make up a database row."""

    @staticmethod
    @abstractmethod
    def get_table_columns() -> list[DataColumn2]:
        """Returns the flet columns to be used to display the database."""
