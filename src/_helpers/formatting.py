"""Shared display-formatting helpers."""

import re
from enum import Enum

_PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,50}$")


def enum_label(value: Enum) -> str:
    """Converts an enum member into a human-readable label.

    Args:
        value (Enum): The enum member to format, e.g. `AccountKind.EMERGENCY`.

    Returns:
        str: The formatted label, e.g. "Emergency".
    """
    return value.name.lower().capitalize().replace("_", " ")


def format_amount(value: float, decimals: int = 2) -> str:
    """Formats an amount using '.' as the thousands separator and ',' as the decimal separator.

    Args:
        value (float): The amount to format.
        decimals (int): The number of decimal places to round to and display. Defaults to 2.

    Returns:
        str: The formatted amount, e.g. "1.234,56" for `value=1234.56, decimals=2`.
    """
    return f"{value:,.{decimals}f}".translate(str.maketrans(",.", ".,"))


def parse_amount(raw: str) -> float:
    """Parses a string formatted by `:func:format_amount` (or plain digits) back into a float.

    Args:
        raw (str): The raw string, e.g. "1.234,56", "1234,56", or "1234".

    Returns:
        float: The parsed amount.

    Raises:
        ValueError: If `raw` cannot be parsed as a number.
    """
    return float(raw.replace(".", "").replace(",", "."))


def parse_year(raw: str) -> int:
    """Parses a year typed into a free-text field.

    Args:
        raw (str): The raw string, e.g. "2026".

    Returns:
        int: The parsed year.

    Raises:
        ValueError: If `raw` is blank, isn't all digits, or isn't a positive number.
    """
    raw = raw.strip()
    if not raw.isdigit():
        raise ValueError("The year must be a positive whole number.")

    year = int(raw)
    if year <= 0:
        raise ValueError("The year must be a positive whole number.")

    return year


def validate_profile_name(raw: str) -> str:
    """Validates a profile name typed into a free-text field.

    The name is embedded directly into a database file name, so it's restricted to characters
    that are always safe there.

    Args:
        raw (str): The raw string, e.g. "Shared".

    Returns:
        str: `raw`, stripped of surrounding whitespace.

    Raises:
        ValueError: If the stripped name is empty or contains characters other than letters,
            digits, hyphens, and underscores.
    """
    raw = raw.strip()
    if not _PROFILE_NAME_PATTERN.fullmatch(raw):
        raise ValueError("The profile name must use only letters, digits, '-', and '_' (1-50 characters).")

    return raw
