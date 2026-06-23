"""Implementation of the `:class:Expense` class."""

from dataclasses import fields
from enum import Enum, auto
from logging import getLogger
from typing import Self

from flet import Alignment, Container, MainAxisAlignment, Row, Text
from flet_datatable2 import DataColumn2, DataColumnSize
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from helpers.constants import EXPENSES_DB_NAME

logger = getLogger("financial_tracker")


class Categories(Enum):
    """Enum with all the possible categories of expenses."""

    COUPLE = auto()
    EDUCATION = auto()
    ENTERTAINMENT = auto()
    FOOD_AND_DRINKS = auto()
    SUBSCRIPTIONS = auto()
    PERSONAL_ITEMS = auto()
    PRESENTS = auto()
    TRAVEL = auto()
    OTHER = auto()


@dataclass(frozen=True, kw_only=True)
class Expense:
    """Expense blueprint.

    Attributes:
        month (int): The month of the expense (between 1 and 12).
        day_start (int): The day of the expense (between 1 and 31). If the expense refers
            to a period of time longer than 1 day, this is the initial day.
        day_start (int): The final day of the expense if said expense refers to a period
            of time longer than 1 day (between `day_start` and 31).
            Otherwise, defaults to `None`.
        description (str): The description of the expense.
        category (Categories): The category of the expense. See `:enum:Categories`.
        cost (float): The cost of the expense (greater than zero).
    """

    month: int = Field(gt=0, lt=13)
    day_start: int = Field(gt=0, lt=32)
    day_end: int | None = Field(default=None, gt=0, lt=32)
    description: str
    category: Categories
    cost: float = Field(gt=0.0)

    @model_validator(mode="after")
    def valid_day_end(self) -> Self:
        """Validates the `day_end` attribute."""
        if self.day_end is not None and self.day_end < self.day_start:
            raise ValueError("End date cannot be before start date.")

        return self

    def __sub__(self, other: Self) -> dict:
        """Subtraction operator overloading.

        Args:
            other (`:class:Expense`): The object to subtract.

        Returns:
            dict: A dictionary with the differences between the instance and the
                other object. In particular, only the values of `other` that
                differ from `self`.
        """
        if not isinstance(other, Expense):
            return NotImplemented

        differences = {}
        for field in fields(self):
            v_self = getattr(self, field.name)
            v_other = getattr(other, field.name)
            if v_self != v_other:
                differences[field.name] = v_other

        return differences

    @classmethod
    def init_from_tuple(cls, fields: tuple[int, int, int, str, str, float]) -> Self:
        """Returns an instance of the class from a tuple.

        It is meant to be used to reconstruct an expense from a row of the
        database after sqlite has fetched it.

        Args:
            fields (tuple): A tuple with the values with which to initialize the class.

        Returns:
            `:class:Expense`: An instance of the class with the desired values.
        """
        logger.info("Called 'init_from_tuple'")

        month, day_start, day_end, description, category, cost = fields
        return cls(
            month=month,
            day_start=day_start,
            day_end=day_end,
            description=description,
            category=Categories[category],
            cost=cost,
        )

    @staticmethod
    def create_table() -> str:
        """Generates the sqlite command to create a table based on the attributes of the class."""
        logger.info("Called 'Expense.create_table'")

        return f"""
            CREATE TABLE IF NOT EXISTS {EXPENSES_DB_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month INTEGER NOT NULL,
                day_start INTEGER NOT NULL,
                day_end INTEGER,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                cost REAL NOT NULL
            )
        """

    @staticmethod
    def get_table_columns() -> list[DataColumn2]:
        """Returns the flet columns to be used to display the database."""
        logger.info("Called 'get_table_columns'")

        return [
            DataColumn2(
                label=Row(controls=[Text("M")], tight=True, spacing=0, alignment=MainAxisAlignment.CENTER),
                numeric=True,
                fixed_width=80,
            ),
            DataColumn2(label=Container(Text("D"), alignment=Alignment.CENTER), fixed_width=100),
            DataColumn2(label=Text("Description"), size=DataColumnSize.S),
            DataColumn2(label=Text("Category"), fixed_width=200),
            DataColumn2(label=Text("Cost (€)"), numeric=True, fixed_width=100),
        ]
