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
HOLDINGS_DB_NAME = "holdings"
HOLDING_REGION_ALLOCATIONS_DB_NAME = "holding_region_allocations"
HOLDING_KIND_TARGETS_DB_NAME = "holding_kind_targets"
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

# the iCloud Drive folder shared with the iPhone Shortcut that captures expenses on the go:
# the Shortcut appends to `INBOX_FILE_NAME`, the app drains it at launch and writes the two
# lookup exports back so the Shortcut's pickers can never drift from the real lists
ICLOUD_DIRECTORY = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Financial Tracker"
INBOX_FILE_NAME = "inbox.jsonl"
INBOX_IMPORTED_FILE_NAME = "imported.jsonl"
INBOX_REJECTED_FILE_NAME = "rejected.jsonl"
# newline-delimited rather than JSON: the only consumer is the iPhone Shortcut, and its
# "Split Text by New Lines -> Choose from List" path is far more dependable than asking it to
# parse a JSON array (whose dictionary handling shows keys with value previews, not a flat list)
INBOX_CATEGORIES_FILE_NAME = "categories.txt"
INBOX_PROFILES_FILE_NAME = "profiles.txt"

# the two archive files are append-only, so they get trimmed back to their most recent lines
# every time something is added to them: they are an audit trail, not the system of record
INBOX_ARCHIVE_MAX_LINES = 1000
