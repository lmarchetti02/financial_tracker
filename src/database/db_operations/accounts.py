"""Implementation of the main operations on the accounts database."""

import sqlite3 as sq
from logging import getLogger

import numpy as np

from _helpers.constants import ACCOUNT_BALANCES_DB_NAME, ACCOUNTS_DB_NAME

from ..data_structures import Account, AccountBalance, AccountKind
from .generic import WhichDb, add_item, edit_item, fetch_by_id, get_db_path, initialize_db, remove_item

logger = getLogger("financial_tracker")


def fetch_account_definitions(year: int) -> list[tuple[int, Account]]:
    """Fetches every account defined for the year, ordered by kind, then name.

    Args:
        year (int): The year of the accounts in the database.

    Returns:
        list[tuple[int, Account]]: The id and the reconstructed `:class:Account` for each row.
    """
    logger.info("Called 'fetch_account_definitions'")

    with sq.connect(get_db_path(year)) as connection:
        rows = connection.execute(f"SELECT * FROM {ACCOUNTS_DB_NAME} ORDER BY kind, name").fetchall()

    return [(row[0], Account.init_from_tuple(row[1:])) for row in rows]


def fetch_account_balances(year: int) -> dict[tuple[int, int], float]:
    """Fetches every logged balance for the year.

    Args:
        year (int): The year of the balances in the database.

    Returns:
        dict[tuple[int, int], float]: Maps `(account_id, month)` to the logged balance.
    """
    logger.info("Called 'fetch_account_balances'")

    with sq.connect(get_db_path(year)) as connection:
        rows = connection.execute(f"SELECT account_id, month, balance FROM {ACCOUNT_BALANCES_DB_NAME}").fetchall()

    return {(row[0], row[1]): row[2] for row in rows}


def fetch_balances_by_kind(year: int) -> dict[AccountKind, np.ndarray]:
    """Fetches the total balance per month for each account kind that has any balance logged.

    Args:
        year (int): The year of the accounts in the database.

    Returns:
        dict[AccountKind, np.ndarray]: Maps each `:enum:AccountKind` present in the data to an
            array of shape (12,) with its combined balance per month, summed across every
            account of that kind. A kind with no balances logged at all is omitted.
    """
    logger.info("Called 'fetch_balances_by_kind'")

    with sq.connect(get_db_path(year)) as connection:
        rows = connection.execute(
            f"""
            SELECT a.kind, b.month, SUM(b.balance)
            FROM {ACCOUNT_BALANCES_DB_NAME} b
            JOIN {ACCOUNTS_DB_NAME} a ON a.id = b.account_id
            GROUP BY a.kind, b.month
            """
        ).fetchall()

    totals: dict[AccountKind, np.ndarray] = {}
    for kind_name, month, total in rows:
        kind = AccountKind[kind_name]
        totals.setdefault(kind, np.zeros(12, dtype=np.float32))[month - 1] = total

    return totals


def _fetch_balance_id(year: int, account_id: int, month: int) -> int | None:
    """Fetches the id of the balance row for `account_id`/`month`, if any."""
    with sq.connect(get_db_path(year)) as connection:
        row = connection.execute(
            f"SELECT id FROM {ACCOUNT_BALANCES_DB_NAME} WHERE account_id = ? AND month = ?",
            (account_id, month),
        ).fetchone()

    return row[0] if row is not None else None


def save_balance(year: int, account_id: int, month: int, balance: float) -> None:
    """Creates or updates the balance snapshot for one account/month.

    Args:
        year (int): The desired year.
        account_id (int): The id of the `:class:Account` this balance belongs to.
        month (int): The month of the snapshot (between 1 and 12).
        balance (float): The account's total balance in € at the end of `month`.
    """
    logger.info("Called 'save_balance'")

    existing_id = _fetch_balance_id(year, account_id, month)
    new_balance = AccountBalance(account_id=account_id, month=month, balance=balance)

    if existing_id is None:
        add_item(year, new_balance)
    else:
        old_balance = fetch_by_id(year, WhichDb.ACCOUNT_BALANCES, existing_id)
        edit_item(year, existing_id, old_balance, new_balance)

    logger.debug(f"Saved balance:\n{new_balance}")


def delete_balance(year: int, account_id: int, month: int) -> None:
    """Deletes the balance snapshot for one account/month, if any.

    Args:
        year (int): The desired year.
        account_id (int): The id of the `:class:Account` this balance belongs to.
        month (int): The month of the snapshot to delete (between 1 and 12).
    """
    logger.info("Called 'delete_balance'")

    with sq.connect(get_db_path(year)) as connection:
        connection.execute(
            f"DELETE FROM {ACCOUNT_BALANCES_DB_NAME} WHERE account_id = ? AND month = ?", (account_id, month)
        )


def delete_account(year: int, account_id: int) -> bool:
    """Deletes an account together with every balance snapshot logged for it.

    Args:
        year (int): The desired year.
        account_id (int): The id of the account to delete.

    Returns:
        bool: `True` if the account was found and deleted, `False` otherwise.
    """
    logger.info("Called 'delete_account'")

    with sq.connect(get_db_path(year)) as connection:
        connection.execute(f"DELETE FROM {ACCOUNT_BALANCES_DB_NAME} WHERE account_id = ?", (account_id,))

    return remove_item(year, WhichDb.ACCOUNTS, account_id)


def _existing_years_before(before_year: int) -> list[int]:
    """Lists the years, older than `before_year`, that have an existing database file."""
    # derived from `get_db_path` (rather than importing `APP_DIRECTORY` directly) so this keeps
    # resolving correctly even when `APP_DIRECTORY` is monkeypatched (e.g. under test)
    app_directory = get_db_path(before_year).parent

    years = []
    for path in app_directory.glob("*_data.db"):
        try:
            year = int(path.stem.removesuffix("_data"))
        except ValueError:
            continue
        if year < before_year:
            years.append(year)

    return years


def _find_latest_year_with_accounts(before_year: int) -> int | None:
    """Finds the most recent year before `before_year` whose database has any accounts."""
    for year in sorted(_existing_years_before(before_year), reverse=True):
        try:
            if fetch_account_definitions(year):
                return year
        except sq.OperationalError:
            # the year's database predates the `accounts` table
            continue

    return None


def seed_accounts_for_new_year(year: int) -> None:
    """Copies the account definitions from the most recent prior year, if `year` has none yet.

    Balances are never copied, only account names and kinds.

    Args:
        year (int): The desired year.
    """
    logger.info("Called 'seed_accounts_for_new_year'")

    if fetch_account_definitions(year):
        return

    latest_year = _find_latest_year_with_accounts(year)
    if latest_year is None:
        return

    for _, account in fetch_account_definitions(latest_year):
        add_item(year, Account(name=account.name, kind=account.kind))

    logger.debug(f"Seeded accounts for {year} from {latest_year}.")


def fetch_previous_year_account_ids(year: int) -> dict[str, int]:
    """Maps each account name to its id in `year - 1`'s database, if that year exists.

    Args:
        year (int): The current year; accounts are looked up in `year - 1`.

    Returns:
        dict[str, int]: Maps account name to its id in the previous year's database. Empty if
            the previous year has no database file, or it predates the `accounts` table.
    """
    logger.info("Called 'fetch_previous_year_account_ids'")

    previous_year = year - 1
    if not get_db_path(previous_year).exists():
        return {}

    try:
        prior_accounts = fetch_account_definitions(previous_year)
    except sq.OperationalError:
        # the previous year's database predates the `accounts` table
        return {}

    return {account.name: account_id for account_id, account in prior_accounts}


def fetch_previous_year_end_balances(year: int) -> dict[str, float]:
    """Fetches each account's logged December balance from `year - 1`, keyed by account name.

    Args:
        year (int): The current year; balances are looked up in `year - 1`.

    Returns:
        dict[str, float]: Maps account name to its December balance in the previous year.
            Only includes accounts that actually had a December balance logged.
    """
    logger.info("Called 'fetch_previous_year_end_balances'")

    previous_year = year - 1
    account_ids = fetch_previous_year_account_ids(year)
    if not account_ids:
        return {}

    try:
        prior_balances = fetch_account_balances(previous_year)
    except sq.OperationalError:
        # the previous year's database predates the `account_balances` table
        return {}

    return {
        name: prior_balances[(account_id, 12)]
        for name, account_id in account_ids.items()
        if (account_id, 12) in prior_balances
    }


def save_previous_year_end_balance(year: int, account_name: str, kind: AccountKind, balance: float) -> None:
    """Saves `balance` as the December snapshot for `account_name` in `year - 1`'s database.

    This is how the "previous year" column in the balance grid stays in sync with the account's
    actual December row in last year's database, rather than duplicating a separate value. If
    the previous year's database, or a matching account within it, doesn't exist yet, both are
    created — logging this column never requires the previous year to have been used already.

    Args:
        year (int): The current year; the sync target is `year - 1`.
        account_name (str): The name of the account to match (or create) in the previous
            year's database.
        kind (AccountKind): The kind to use if the account has to be created there.
        balance (float): The balance to log for December of the previous year.
    """
    logger.info("Called 'save_previous_year_end_balance'")

    previous_year = year - 1
    initialize_db(previous_year, WhichDb.ACCOUNTS)
    initialize_db(previous_year, WhichDb.ACCOUNT_BALANCES)

    account_id = fetch_previous_year_account_ids(year).get(account_name)
    if account_id is None:
        account_id = add_item(previous_year, Account(name=account_name, kind=kind))
        logger.debug(f"Created '{account_name}' ({kind.name}) in {previous_year} to sync its December balance.")

    save_balance(previous_year, account_id, 12, balance)


def delete_previous_year_end_balance(year: int, account_name: str) -> None:
    """Clears the December snapshot for `account_name` in `year - 1`'s database, if any.

    Args:
        year (int): The current year; the sync target is `year - 1`.
        account_name (str): The name of the account to match in the previous year's database.
    """
    logger.info("Called 'delete_previous_year_end_balance'")

    account_id = fetch_previous_year_account_ids(year).get(account_name)
    if account_id is None:
        return

    delete_balance(year - 1, account_id, 12)
