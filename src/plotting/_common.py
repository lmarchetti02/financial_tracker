"""Private helpers shared across the plotting modules."""

import flet as ft

from database import DbLocation


def current_db_location(page: ft.Page) -> DbLocation:
    """Reads the currently selected year/profile from `page.session.store`.

    Args:
        page (ft.Page): The page object.

    Returns:
        `:class:database.DbLocation`: The selected year/profile.

    Raises:
        RuntimeError: If either hasn't been set yet.
    """
    if (year := page.session.store.get("selected_year")) is None:
        raise RuntimeError("Cannot retrieve the current year.")

    if (profile := page.session.store.get("selected_profile")) is None:
        raise RuntimeError("Cannot retrieve the current profile.")

    return DbLocation(int(year), profile)
