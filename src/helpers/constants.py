"""Module woth useful constants across the application."""

from os import getenv

DEBUGGING = getenv("DEBUGGING", "False").lower() == "true"
DB_DIRECTORY = ".financial_tracker"
DB_NAME = "expenses"
