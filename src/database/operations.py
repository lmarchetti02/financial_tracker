"""Implementation of the main operations on the expenses database."""

import sqlite3 as sq
from logging import getLogger
from pathlib import Path

from helpers.constants import DB_DIRECTORY, DB_NAME

from .expense import Expense

logger = getLogger("financial_tracker")


def initialize_db(year: int) -> None:
    """Initializes the database if it doesn't already exist.

    Args:
        year (int): The year of the expenses in the database.
    """
    logger.info("Called 'initialize_db'.")

    # create necessary dir
    app_dir = Path.home() / DB_DIRECTORY
    app_dir.mkdir(parents=True, exist_ok=True)
    db_path = app_dir / (DB_NAME + f"_{year}.db")
    logger.debug("Created database dir if it didn't already exist.")

    # create database
    with sq.connect(str(db_path)) as connection:
        # create cursor
        cursor = connection.cursor()

        # create table
        cursor.execute(Expense.create_table())

        # create index on categories for more efficient filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON expenses(category)")
        logger.debug(f"Created table inside {db_path} if it didn't already exist.")


def add_expense(year: int, expense: Expense):
    """Adds an expense to the database."""
    logger.info("Called 'add_expense'.")

    with sq.connect(str(Path.home() / DB_DIRECTORY / (DB_NAME + f"_{year}.db"))) as connection:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO {DB_NAME} (month, day_start, day_end, description, category, cost)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                expense.month,
                expense.day_start,
                expense.day_end,
                expense.description,
                expense.category.name,
                expense.cost,
            ),
        )
        logger.debug(f"Added expense to the database:\n{expense}.")
