"""Sub-package holding the settings view: one panel per group of settings."""

from collections.abc import Callable

import flet as ft

from .view import SettingsView as SettingsView


def settings_view(page: ft.Page, on_change_year: Callable[[ft.Event], None]) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return SettingsView(page, on_change_year)
