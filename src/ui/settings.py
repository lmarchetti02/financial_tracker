"""Implementation of the settings layout."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

import database as db

from .common import current_db_location, show_alert

logger = getLogger("financial_tracker")


class SettingsView(ft.Column):
    """Encapsulates the settings view: current year, theme, and category/source/kind management."""

    def __init__(self, page: ft.Page, on_change_year: Callable[[ft.Event], None]) -> None:
        """Initializes the view."""
        super().__init__()
        self._page = page
        self._lookup_lists: dict[db.LookupKind, ft.Column] = {}

        location = current_db_location(page)

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.scroll = ft.ScrollMode.AUTO

        year_section = ft.Row(
            controls=[
                ft.Text(f"Current year: {location.year} · Profile: {location.profile}", size=18),
                ft.Button("Change Year/Profile", on_click=on_change_year),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        theme_switch = ft.Switch(
            label="Dark theme",
            value=page.theme_mode == ft.ThemeMode.DARK,
            on_change=self._handle_theme_change,
        )

        password_set = db.is_password_set()
        self._password_switch = ft.Switch(
            label="Require password at startup",
            value=password_set,
            on_change=self._handle_password_switch_change,
        )
        self._change_password_button = ft.Button(
            "Change Password",
            icon=ft.Icons.LOCK_OUTLINE,
            visible=password_set,
            on_click=self._change_password,
        )

        recompute_button = ft.Button(
            "Recompute Debt/Credit Balances",
            icon=ft.Icons.SYNC,
            on_click=self._handle_recompute_debt_credit_balances,
        )

        self.controls = [
            ft.Text("Settings", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=40),
            year_section,
            ft.Container(height=20),
            theme_switch,
            ft.Container(height=20),
            self._password_switch,
            self._change_password_button,
            ft.Container(height=20),
            recompute_button,
            ft.Container(height=30),
            ft.Row(
                controls=[
                    self._build_lookup_section(db.LookupKind.CATEGORIES, "Categories (Expense)", "category"),
                    self._build_lookup_section(db.LookupKind.SOURCES, "Sources (Income)", "source"),
                    self._build_lookup_section(db.LookupKind.KINDS, "Kinds (Transfer)", "kind"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=60,
            ),
        ]

    def _handle_theme_change(self, e: ft.Event) -> None:
        """Toggles and persists the app's theme mode."""
        logger.info("Called '_handle_theme_change'")

        mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self._page.theme_mode = mode
        db.set_theme_preference("dark" if mode == ft.ThemeMode.DARK else "light")
        self._page.update()

    def _handle_recompute_debt_credit_balances(self, _: ft.Event) -> None:
        """Rebuilds every Debt/Credit account's balances, across every year and profile, from their transfers."""
        logger.info("Called '_handle_recompute_debt_credit_balances'")

        created = db.recompute_all_debt_credit_balances()

        if created:
            details = ", ".join(f"{name} ({year}, {profile})" for year, profile, name in sorted(set(created)))
            show_alert(
                self._page,
                "Recomputed — review new accounts' opening balances",
                f"Assumed €0 as the starting balance for newly created accounts: {details}. If "
                "any of these owed/were owed something before their earliest tracked transfer, "
                "set the correct opening balance via the 'previous year' column in Accounts, for "
                "the year/profile shown — it will then carry forward automatically into later years.",
            )
        else:
            show_alert(
                self._page,
                "Balances recomputed",
                "Every Debt/Credit account's balances were rebuilt from their linked transfers.",
            )

    def _handle_password_switch_change(self, e: ft.Event) -> None:
        """Opens the set-password dialog when switched on, or the remove-password one when off."""
        logger.info("Called '_handle_password_switch_change'")

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

        self._show_password_dialog("Set Password", [new_field, confirm_field], "Save", save)

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
                self._refresh_password_controls()
                return

            self._save_password(new_field.value or "", confirm_field.value or "", "Cannot change password")

        self._show_password_dialog("Change Password", [current_field, new_field, confirm_field], "Save", save)

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

            self._refresh_password_controls()

        self._show_password_dialog("Remove Password", [current_field], "Remove", remove)

    def _save_password(self, new_password: str, confirmation: str, error_title: str) -> None:
        """Persists `new_password` if it matches `confirmation` and satisfies the password rules."""
        if new_password != confirmation:
            show_alert(self._page, error_title, "The passwords do not match.")
            self._refresh_password_controls()
            return

        try:
            db.set_app_password(new_password)
        except ValueError as error:
            show_alert(self._page, error_title, str(error))

        self._refresh_password_controls()

    def _show_password_dialog(
        self, title: str, fields: list[ft.TextField], confirm_label: str, on_confirm: Callable[[ft.Event], None]
    ) -> None:
        """Shows a password dialog that re-syncs the switch however it ends up being closed."""

        def cancel(_: ft.Event) -> None:
            """Closes the dialog without changing anything."""
            self._page.pop_dialog()
            self._refresh_password_controls()

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
                on_dismiss=lambda _: self._refresh_password_controls(),
            )
        )

    def _refresh_password_controls(self) -> None:
        """Resets the switch and the change button to whether a password is actually set.

        The switch has already flipped visually by the time its handler runs, so every dialog
        outcome — saved, cancelled or rejected — ends here to put it back in sync.
        """
        password_set = db.is_password_set()
        self._password_switch.value = password_set
        self._change_password_button.visible = password_set
        self._page.update()

    def _build_lookup_section(self, kind: db.LookupKind, title: str, item_label: str) -> ft.Column:
        """Builds one category/source/kind management section (list, add, rename, delete)."""
        list_column = ft.Column(controls=[self._build_lookup_row(kind, o) for o in db.fetch_lookup_options(kind)])
        self._lookup_lists[kind] = list_column

        new_name_field = ft.TextField(label=f"New {item_label}", width=220)

        def add(_: ft.Event) -> None:
            """Adds the entry typed into `new_name_field`."""
            logger.info("Called 'add' lookup option")

            try:
                db.add_lookup_option(kind, new_name_field.value or "")
            except ValueError as error:
                show_alert(self._page, "Cannot add", str(error))
                return

            new_name_field.value = ""
            self._refresh_lookup_list(kind)

        return ft.Column(
            controls=[
                ft.Text(title, weight=ft.FontWeight.BOLD, size=18),
                list_column,
                ft.Row(controls=[new_name_field, ft.Button("Add", on_click=add)]),
            ],
        )

    def _build_lookup_row(self, kind: db.LookupKind, option: db.LookupOption) -> ft.Row:
        """Builds a single entry row with its rename/delete buttons."""
        tooltip = "Required by the app" if option.is_system else None

        return ft.Row(
            controls=[
                ft.Text(option.name, width=180),
                ft.Button(
                    icon=ft.Icons.EDIT,
                    width=50,
                    height=30,
                    color=None if option.is_system else ft.Colors.BLUE,
                    disabled=option.is_system,
                    tooltip=tooltip,
                    on_click=lambda _: self._rename_lookup_option(kind, option.name),
                ),
                ft.Button(
                    icon=ft.Icons.DELETE,
                    width=50,
                    height=30,
                    disabled=option.is_system,
                    tooltip=tooltip,
                    on_click=lambda _: self._delete_lookup_option(kind, option.name),
                ),
            ],
        )

    def _rename_lookup_option(self, kind: db.LookupKind, old_name: str) -> None:
        """Shows a dialog to rename an entry."""
        logger.info("Called '_rename_lookup_option'")

        name_field = ft.TextField(label="Name", value=old_name, autofocus=True)

        def save(_: ft.Event) -> None:
            """Applies the rename, if valid."""
            try:
                db.rename_lookup_option(kind, old_name, name_field.value or "")
            except ValueError as error:
                show_alert(self._page, "Cannot rename", str(error))

            self._page.pop_dialog()
            self._refresh_lookup_list(kind)

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Rename '{old_name}'"),
                content=name_field,
                actions=[
                    ft.TextButton("Save", on_click=save),
                    ft.TextButton("Cancel", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def _delete_lookup_option(self, kind: db.LookupKind, name: str) -> None:
        """Shows a confirmation dialog, then deletes the entry if it's safe to do so."""
        logger.info("Called '_delete_lookup_option'")

        def delete(_: ft.Event) -> None:
            """Actually deletes the entry."""
            success = db.delete_lookup_option(kind, name)
            if not success:
                show_alert(
                    self._page,
                    "Cannot delete",
                    f"'{name}' is required by the app or still used by existing data, so it cannot be deleted.",
                )

            self._page.pop_dialog()
            self._refresh_lookup_list(kind)

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Delete '{name}'"),
                content=ft.Text(f"Are you sure you want to delete '{name}'?"),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def _refresh_lookup_list(self, kind: db.LookupKind) -> None:
        """Rebuilds the displayed rows for one lookup list from the database."""
        self._lookup_lists[kind].controls = [
            self._build_lookup_row(kind, option) for option in db.fetch_lookup_options(kind)
        ]
        self._page.update()


def settings_view(page: ft.Page, on_change_year: Callable[[ft.Event], None]) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return SettingsView(page, on_change_year)
