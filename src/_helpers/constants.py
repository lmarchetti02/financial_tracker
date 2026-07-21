"""Module woth useful constants across the application."""

from os import getenv
from pathlib import Path

DEBUGGING = getenv("DEBUGGING", "False").lower() == "true"

APP_DIRECTORY = Path.home() / ".financial_tracker"
EXPENSES_DB_NAME = "expenses"
INCOME_DB_NAME = "income"
TRANSFERS_DB_NAME = "transfers"
ACCOUNTS_DB_NAME = "accounts"
ACCOUNT_BALANCES_DB_NAME = "account_balances"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
