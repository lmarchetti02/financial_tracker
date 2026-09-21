"""Implementation of the startup-password settings controls and their dialogs."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

import database as db

from ..common import show_alert

logger = getLogger("financial_tracker")


class PasswordSettings:
    """Owns the startup-password switch, its 'Change Password' button, and every related dialog.

    The switch flips visually before its handler runs, so every dialog outcome — saved, cancelled
    or dismissed — ends in `:meth:_refresh_controls` to put it back in sync with what's persisted.
    """

    def __init__(self, page: ft.Page) -> None:
        """Initializes the controls from whether a password is currently set."""
        self._page = page

        password_set = db.is_password_set()
        self.switch = ft.Switch(value=password_set, on_change=self._handle_switch_change)
        self.change_button = ft.Button(
            "Change Password",
            icon=ft.Icons.LOCK_OUTLINE,
            visible=password_set,
            on_click=self._change_password,
        )

    def _handle_switch_change(self, e: ft.Event) -> None:
        """Opens the set-password dialog when switched on, or the remove-password one when off."""
        logger.info("Called '_handle_switch_change'")

        if e.control.value:
            self._set_password()
        else:
            self._remove_password()

    def _set_password(self) -> None:
        """Shows a dialog to set the startup password for the first time."""
        logger.info("Called '_set_password'")

        new_field = ft.TextField(label="New password", password=True, can_reveal_password=True, autofocus=True)
        confirm_field = ft.TextField(label="Confirm new password", password=True, can_reveal_password=True)

        def save(_: ft.Event) -> None:
            """Persists the typed password, if it's valid and both fields match."""
            self._page.pop_dialog()
            self._save_password(new_field.value or "", confirm_field.value or "", "Cannot set password")

        self._show_dialog("Set Password", [new_field, confirm_field], "Save", save)

    def _change_password(self, _: ft.Event) -> None:
        """Shows a dialog to replace the startup password, after confirming the current one."""
        logger.info("Called '_change_password'")

        current_field = ft.TextField(label="Current password", password=True, can_reveal_password=True, autofocus=True)
        new_field = ft.TextField(label="New password", password=True, can_reveal_password=True)
        confirm_field = ft.TextField(label="Confirm new password", password=True, can_reveal_password=True)

        def save(_: ft.Event) -> None:
            """Replaces the password, if the current one is right and both new fields match."""
            self._page.pop_dialog()

            if not db.verify_app_password(current_field.value or ""):
                show_alert(self._page, "Cannot change password", "The current password is not correct.")
                self._refresh_controls()
                return

            self._save_password(new_field.value or "", confirm_field.value or "", "Cannot change password")

        self._show_dialog("Change Password", [current_field, new_field, confirm_field], "Save", save)

    def _remove_password(self) -> None:
        """Shows a dialog to remove the startup password, after confirming the current one."""
        logger.info("Called '_remove_password'")

        current_field = ft.TextField(label="Current password", password=True, can_reveal_password=True, autofocus=True)

        def remove(_: ft.Event) -> None:
            """Removes the password, if the typed current one is right."""
            self._page.pop_dialog()

            if not db.verify_app_password(current_field.value or ""):
                show_alert(self._page, "Cannot remove password", "The current password is not correct.")
            else:
                db.clear_app_password()

            self._refresh_controls()

        self._show_dialog("Remove Password", [current_field], "Remove", remove)

    def _save_password(self, new_password: str, confirmation: str, error_title: str) -> None:
        """Persists `new_password` if it matches `confirmation` and satisfies the password rules."""
        if new_password != confirmation:
            show_alert(self._page, error_title, "The passwords do not match.")
            self._refresh_controls()
            return

        try:
            db.set_app_password(new_password)
        except ValueError as error:
            show_alert(self._page, error_title, str(error))

        self._refresh_controls()

    def _show_dialog(
        self, title: str, fields: list[ft.TextField], confirm_label: str, on_confirm: Callable[[ft.Event], None]
    ) -> None:
        """Shows a password dialog that re-syncs the switch however it ends up being closed."""

        def cancel(_: ft.Event) -> None:
            """Closes the dialog without changing anything."""
            self._page.pop_dialog()
            self._refresh_controls()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(title),
                content=ft.Column(controls=list(fields), tight=True),
                actions=[
                    ft.TextButton(confirm_label, on_click=on_confirm),
                    ft.TextButton("Cancel", on_click=cancel),
                ],
                # dismissing by tapping outside never reaches `cancel`, which would otherwise
                # leave the switch showing the opposite of what's actually persisted
                on_dismiss=lambda _: self._refresh_controls(),
            )
        )

    def _refresh_controls(self) -> None:
        """Resets the switch and the change button to whether a password is actually set."""
        password_set = db.is_password_set()
        self.switch.value = password_set
        self.change_button.visible = password_set
        self._page.update()
