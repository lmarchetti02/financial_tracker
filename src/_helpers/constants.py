"""Module woth useful constants across the application."""

from pathlib import Path

APP_DIRECTORY = Path.home() / "Library" / "Application Support" / "Financial Tracker"
LOG_DIRECTORY = Path.home() / "Library" / "Logs" / "Financial Tracker"
DEFAULT_PROFILE_NAME = "Personal"
EXPENSES_DB_NAME = "expenses"
INCOME_DB_NAME = "income"
TRANSFERS_DB_NAME = "transfers"
ACCOUNTS_DB_NAME = "accounts"
ACCOUNT_BALANCES_DB_NAME = "account_balances"
CONFIG_DB_NAME = "config"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# system-reserved category/source/kind values: `transfers.py` hardcodes these to auto-generate a
# linked expense/income when a transfer has a fee/profit, so they can never be renamed or deleted
SYSTEM_CATEGORY_TRADING_FEE = "Trading fee"
SYSTEM_SOURCE_INVESTMENTS = "Investments"
SYSTEM_KIND_INVESTMENT = "Investment"

# `db_operations.accounts` hardcodes these to auto-create/sync a linked Debt/Credit `Account`
# balance from a transfer's source/destination, so they can never be renamed or deleted either
SYSTEM_KIND_DEBT = "Debt"
SYSTEM_KIND_CREDIT = "Credit"
