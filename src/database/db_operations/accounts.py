"""Implementation of the main operations on the accounts database."""

import sqlite3 as sq
from dataclasses import replace
from logging import getLogger

import numpy as np

from _helpers.constants import (
    ACCOUNT_BALANCES_DB_NAME,
    ACCOUNTS_DB_NAME,
    SYSTEM_KIND_CREDIT,
    SYSTEM_KIND_DEBT,
    TRANSFERS_DB_NAME,
)

from ..data_structures import Account, AccountBalance, AccountKind, Transfer
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


def fetch_net_worth_components(year: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Splits each month's account balances into the components of net worth.

    Args:
        year (int): The year of the accounts in the database.

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]: Four arrays of shape (12,):
            liquid assets (every kind except pension, credit and debt), the pension fund,
            credits, and debts.
    """
    logger.info("Called 'fetch_net_worth_components'")

    totals_by_kind = fetch_balances_by_kind(year)
    pension = totals_by_kind.pop(AccountKind.PENSION, np.zeros(12, dtype=np.float32))
    credits = totals_by_kind.pop(AccountKind.CREDIT, np.zeros(12, dtype=np.float32))
    debts = totals_by_kind.pop(AccountKind.DEBT, np.zeros(12, dtype=np.float32))
    liquid_assets = sum(totals_by_kind.values(), start=np.zeros(12, dtype=np.float32))

    return liquid_assets, pension, credits, debts


def fetch_opening_balances_by_kind(year: int) -> dict[AccountKind, float]:
    """Sums every Debt/Credit account's `opening_balance` for `year`, grouped by kind.

    Args:
        year (int): The year whose accounts to sum.

    Returns:
        dict[AccountKind, float]: Maps `:enum:AccountKind.DEBT`/`.CREDIT` to the summed opening
            balance of every account of that kind in `year`. A kind with no accounts is omitted.
    """
    logger.info("Called 'fetch_opening_balances_by_kind'")

    try:
        accounts = fetch_account_definitions(year)
    except sq.OperationalError:
        # this year's database predates the `accounts` table
        return {}

    totals: dict[AccountKind, float] = {}
    for _, account in accounts:
        if account.kind in (AccountKind.DEBT, AccountKind.CREDIT):
            totals[account.kind] = totals.get(account.kind, 0.0) + account.opening_balance

    return totals


def fetch_previous_year_end_net_worth_components(year: int) -> tuple[float, float, float, float]:
    """Splits the previous year-end's balances into the components of net worth.

    Liquid assets and the pension fund are read from `year - 1`'s own December balances, since
    those account kinds are manually tracked per year like any other. Credits and debts are read
    from `year`'s own accounts' `opening_balance` instead - not from `year - 1`'s database - since
    that's the one place their true previous year-end value is guaranteed to still exist (`year -
    1`'s own account/balance rows are never required to exist, or to stay in sync, for a Debt/
    Credit account's `:func:recompute_account_balance` to be correct).

    Args:
        year (int): The current year; liquid assets/pension are looked up in `year - 1`, credits/
            debts in `year`'s own accounts.

    Returns:
        tuple[float, float, float, float]: The previous year-end's liquid assets, pension fund,
            credits, and debts. Liquid assets/pension default to 0.0 if `year - 1` has no
            database, or it predates the `accounts`/`account_balances` tables.
    """
    logger.info("Called 'fetch_previous_year_end_net_worth_components'")

    previous_year = year - 1
    liquid_assets, pension = 0.0, 0.0
    if get_db_path(previous_year).exists():
        try:
            liquid_assets_by_month, pension_by_month, _, _ = fetch_net_worth_components(previous_year)
            liquid_assets, pension = float(liquid_assets_by_month[11]), float(pension_by_month[11])
        except sq.OperationalError:
            pass

    opening_by_kind = fetch_opening_balances_by_kind(year)
    credits = opening_by_kind.get(AccountKind.CREDIT, 0.0)
    debts = opening_by_kind.get(AccountKind.DEBT, 0.0)

    return liquid_assets, pension, credits, debts


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

    Monthly balances are never copied. For Debt/Credit accounts, the copy's `opening_balance` is
    set to the source year's final (December) balance, so `year`'s own recompute continues
    seamlessly from where the prior year left off, without reaching into that year's database.

    Args:
        year (int): The desired year.
    """
    logger.info("Called 'seed_accounts_for_new_year'")

    if fetch_account_definitions(year):
        return

    latest_year = _find_latest_year_with_accounts(year)
    if latest_year is None:
        return

    prior_balances = fetch_account_balances(latest_year)
    for prior_id, account in fetch_account_definitions(latest_year):
        opening_balance = 0.0
        if account.kind in (AccountKind.DEBT, AccountKind.CREDIT):
            opening_balance = prior_balances.get((prior_id, 12), 0.0)
        add_item(year, Account(name=account.name, kind=account.kind, opening_balance=opening_balance))

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


def get_or_create_debt_credit_account(year: int, name: str, kind: AccountKind) -> tuple[int, bool]:
    """Finds the account named `name` (case-insensitively), creating it if it doesn't exist.

    Args:
        year (int): The desired year.
        name (str): The account name, as taken from a transfer's `source`/`destination`.
        kind (`:enum:AccountKind`): The kind to create the account with, if it has to be created.

    Returns:
        tuple[int, bool]: The id of the matching (or newly created) account, and whether it was
            just created rather than matched to an existing one. A newly created account defaults
            its `opening_balance` to 0.0 - worth reviewing if the account's real balance predates
            this, its earliest tracked transfer.

    Raises:
        ValueError: If an account named `name` already exists with a different kind. Account
            names are unique per year regardless of kind (see `ui.accounts.AccountsView.add_account`),
            so this means `name` collides with an unrelated, already-tracked account.
    """
    logger.info("Called 'get_or_create_debt_credit_account'")

    for account_id, account in fetch_account_definitions(year):
        if account.name.lower() == name.lower():
            if account.kind is not kind:
                raise ValueError(
                    f"An account named '{account.name}' already exists as {account.kind.name}, not {kind.name}."
                )
            return account_id, False

    account_id = add_item(year, Account(name=name, kind=kind))
    logger.debug(f"Created '{name}' ({kind.name}) account {account_id} for {year}.")

    return account_id, True


def save_account_opening_balance(year: int, account_id: int, balance: float) -> None:
    """Sets a Debt/Credit account's opening balance and recomputes its balances for `year`.

    The opening balance represents the account's true balance immediately before month 1 of
    `year` - the one manually-set starting point its monthly balances (computed from linked
    transfers) build on top of. Unlike a regular account's "previous year" balance, it's never
    read from or written to another year's database, so a later recompute of another year can
    never silently overwrite it.

    Args:
        year (int): The desired year.
        account_id (int): The id of the `:class:Account` to update.
        balance (float): The account's true balance immediately before month 1 of `year`.
    """
    logger.info("Called 'save_account_opening_balance'")

    account = fetch_by_id(year, WhichDb.ACCOUNTS, account_id)
    edit_item(year, account_id, account, replace(account, opening_balance=balance))
    recompute_account_balance(year, account_id)


def _fetch_debt_credit_transfers(year: int, kind_label: str, account_name: str) -> list[Transfer]:
    """Fetches every transfer of `kind_label` naming `account_name` as source or destination.

    Args:
        year (int): The year of the transfers in the database.
        kind_label (str): The transfer `kind` to match (`SYSTEM_KIND_DEBT` or `SYSTEM_KIND_CREDIT`).
        account_name (str): The account name to match, case-insensitively, against source/destination.

    Returns:
        list[Transfer]: The matching transfers, ordered by month, then day, then id.
    """
    with sq.connect(get_db_path(year)) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM {TRANSFERS_DB_NAME}
            WHERE kind = ? AND (LOWER(source) = LOWER(?) OR LOWER(destination) = LOWER(?))
            ORDER BY month, day, id
            """,
            (kind_label, account_name, account_name),
        ).fetchall()

    return [Transfer.init_from_tuple(row[1:]) for row in rows]


def _signed_delta(transfer: Transfer, account_name: str, kind: AccountKind) -> float:
    """Returns the signed effect of `transfer` on `account_name`'s balance.

    Named as source, money flows from the account to you: a `:enum:AccountKind.DEBT` balance
    increases (you borrowed) and a `:enum:AccountKind.CREDIT` balance decreases (they repaid you).
    Named as destination, money flows from you to the account, so the effect is reversed.
    """
    sign = 1.0 if kind is AccountKind.DEBT else -1.0

    delta = 0.0
    if transfer.source is not None and transfer.source.lower() == account_name.lower():
        delta += sign * transfer.amount
    if transfer.destination is not None and transfer.destination.lower() == account_name.lower():
        delta -= sign * transfer.amount

    return delta


def recompute_account_balance(year: int, account_id: int) -> None:
    """Rebuilds every monthly balance of a Debt/Credit account from its linked transfers.

    Replays every Debt/Credit transfer naming this account, starting from its own
    `:attr:Account.opening_balance`, and overwrites the account's balance for every month of
    `year`. A no-op for any account whose kind isn't `:enum:AccountKind.DEBT`/`.CREDIT`. Never
    reads another year's data to compute `year`'s own balances - the opening balance is always
    `year`'s own field, immune to another year's recompute. It does, however, propagate its
    resulting December balance forward into `year + 1`'s matching account's `opening_balance` (and
    recompute that year too, cascading as far forward as data exists), if that year already has a
    matching account whose opening balance is out of date - this is what keeps a correction made
    in one year visible in every later year, without requiring each of them to be reopened by hand.

    Args:
        year (int): The year to recompute balances for.
        account_id (int): The id of the `:class:Account` to recompute.
    """
    logger.info("Called 'recompute_account_balance'")

    account = fetch_by_id(year, WhichDb.ACCOUNTS, account_id)
    if account.kind not in (AccountKind.DEBT, AccountKind.CREDIT):
        return

    kind_label = SYSTEM_KIND_DEBT if account.kind is AccountKind.DEBT else SYSTEM_KIND_CREDIT
    transfers = _fetch_debt_credit_transfers(year, kind_label, account.name)

    deltas_by_month: dict[int, float] = {}
    for transfer in transfers:
        deltas_by_month[transfer.month] = deltas_by_month.get(transfer.month, 0.0) + _signed_delta(
            transfer, account.name, account.kind
        )

    running = account.opening_balance
    for month in range(1, 13):
        running += deltas_by_month.get(month, 0.0)
        save_balance(year, account_id, month, running)

    logger.debug(f"Recomputed {year} balances for account {account_id} ('{account.name}').")

    _cascade_opening_balance_forward(year, account.name, account.kind, running)


def _cascade_opening_balance_forward(year: int, account_name: str, kind: AccountKind, december_balance: float) -> None:
    """Propagates `year`'s December balance into `year + 1`'s matching account, if any.

    A no-op if `year + 1` has no database, no matching account, or that account's opening balance
    already matches (nothing changed, so there's nothing to propagate further forward).
    """
    next_year = year + 1
    if not get_db_path(next_year).exists():
        return

    try:
        next_year_accounts = fetch_account_definitions(next_year)
    except sq.OperationalError:
        # `next_year`'s database predates the `accounts` table
        return

    for next_account_id, next_account in next_year_accounts:
        if next_account.name.lower() != account_name.lower() or next_account.kind is not kind:
            continue
        if next_account.opening_balance == december_balance:
            return

        edit_item(next_year, next_account_id, next_account, replace(next_account, opening_balance=december_balance))
        recompute_account_balance(next_year, next_account_id)
        return


def sync_transfer_accounts(year: int, transfer: Transfer) -> list[str]:
    """Creates/updates the Debt or Credit account(s) named in a transfer's source/destination.

    A no-op for any transfer whose `kind` isn't `SYSTEM_KIND_DEBT`/`SYSTEM_KIND_CREDIT`.

    Args:
        year (int): The year the transfer belongs to.
        transfer (Transfer): The transfer to sync. Call this once for the old version and once
            for the new version of an edited transfer, and once for a deleted transfer (after
            removing it), so every account it could have affected gets recomputed.

    Returns:
        list[str]: The names of any account newly created by this sync - worth surfacing to the
            user, since a fresh account's opening balance defaults to 0.0 and may need setting if
            its real balance predates this transfer.

    Raises:
        ValueError: Propagated from `get_or_create_debt_credit_account` if `transfer.source`/
            `transfer.destination` names an existing account of a different kind.
    """
    logger.info("Called 'sync_transfer_accounts'")

    if transfer.kind == SYSTEM_KIND_DEBT:
        kind = AccountKind.DEBT
    elif transfer.kind == SYSTEM_KIND_CREDIT:
        kind = AccountKind.CREDIT
    else:
        return []

    created_names = []
    for name in (transfer.source, transfer.destination):
        if name is None:
            continue
        account_id, was_created = get_or_create_debt_credit_account(year, name, kind)
        if was_created:
            created_names.append(name)
        recompute_account_balance(year, account_id)

    return created_names


def recompute_all_debt_credit_balances() -> list[tuple[int, str]]:
    """Rebuilds every Debt/Credit account's balances, across every year, from scratch.

    Backfills accounts/balances for Debt/Credit transfers logged before this syncing existed, and
    doubles as a general "fix drift" tool. Years are processed oldest first so each year's
    December balance is seeded forward via `seed_accounts_for_new_year`'s `opening_balance` copy,
    not by reading another year's data during recompute itself.

    Returns:
        list[tuple[int, str]]: `(year, account_name)` pairs for accounts newly created by this
            run - worth reviewing, since a fresh account's opening balance defaults to 0.0 and may
            need setting if its real balance predates its earliest tracked transfer.
    """
    logger.info("Called 'recompute_all_debt_credit_balances'")

    # derived from `get_db_path` (rather than importing `APP_DIRECTORY` directly) so this keeps
    # resolving correctly even when `APP_DIRECTORY` is monkeypatched (e.g. under test)
    app_directory = get_db_path(0).parent

    years = []
    for path in app_directory.glob("*_data.db"):
        try:
            years.append(int(path.stem.removesuffix("_data")))
        except ValueError:
            continue

    created = []
    for year in sorted(years):
        initialize_db(year, WhichDb.ACCOUNTS)
        initialize_db(year, WhichDb.ACCOUNT_BALANCES)

        for kind_label, kind in ((SYSTEM_KIND_DEBT, AccountKind.DEBT), (SYSTEM_KIND_CREDIT, AccountKind.CREDIT)):
            with sq.connect(get_db_path(year)) as connection:
                try:
                    rows = connection.execute(
                        f"SELECT source, destination FROM {TRANSFERS_DB_NAME} WHERE kind = ?", (kind_label,)
                    ).fetchall()
                except sq.OperationalError:
                    # this year's database predates the `transfers` table
                    continue

            names = {name for row in rows for name in row if name is not None}
            for name in names:
                account_id, was_created = get_or_create_debt_credit_account(year, name, kind)
                if was_created:
                    created.append((year, name))
                recompute_account_balance(year, account_id)

    logger.debug("Recomputed every Debt/Credit account's balances across all years.")

    return created
