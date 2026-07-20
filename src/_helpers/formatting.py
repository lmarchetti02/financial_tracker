"""Shared display-formatting helpers."""

from enum import Enum


def enum_label(value: Enum) -> str:
    """Converts an enum member into a human-readable label.

    Args:
        value (Enum): The enum member to format, e.g. `Categories.FOOD_AND_DRINKS`.

    Returns:
        str: The formatted label, e.g. "Food and drinks".
    """
    return value.name.lower().capitalize().replace("_", " ")
