"""Implementation of the `:class:Expense` class."""

from enum import Enum, auto
from logging import getLogger
from typing import Self

from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from helpers.constants import DB_NAME

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

    @staticmethod
    def create_table() -> str:
        """Generates the sqlite command to create a table based on the attributes of the class."""
        logger.info("Called 'Expense.create_table'")

        return f"""
            CREATE TABLE IF NOT EXISTS {DB_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month INTEGER NOT NULL,
                day_start INTEGER NOT NULL,
                day_end INTEGER,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                cost REAL NOT NULL
            )
        """
