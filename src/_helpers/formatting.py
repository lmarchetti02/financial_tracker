"""Shared display-formatting helpers."""

from enum import Enum


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
