"""Module woth useful constants across the application."""

from os import getenv
from pathlib import Path

DEBUGGING = getenv("DEBUGGING", "False").lower() == "true"

DB_DIRECTORY = Path.home() / ".financial_tracker"
DB_NAME = "expenses"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
