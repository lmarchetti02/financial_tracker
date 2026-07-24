"""Implementation of the settings layout."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

import database as db

from .common import show_alert

logger = getLogger("financial_tracker")


class SettingsView(ft.Column):
    """Encapsulates the settings view: current year, theme, and category/source/kind management."""

    def __init__(self, page: ft.Page, on_change_year: Callable[[ft.Event], None]) -> None:
        """Initializes the view."""
        super().__init__()
        self._page = page
        self._lookup_lists: dict[db.LookupKind, ft.Column] = {}

        if (year := page.session.store.get("selected_year")) is None:
            raise RuntimeError("Cannot retrieve the current year.")

        if (profile := page.session.store.get("selected_profile")) is None:
            raise RuntimeError("Cannot retrieve the current profile.")

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.scroll = ft.ScrollMode.AUTO

        year_section = ft.Row(
            controls=[
                ft.Text(f"Current year: {year} · Profile: {profile}", size=18),
                ft.Button("Change Year/Profile", on_click=on_change_year),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        theme_switch = ft.Switch(
            label="Dark theme",
            value=page.theme_mode == ft.ThemeMode.DARK,
            on_change=self._handle_theme_change,
        )

        recompute_button = ft.Button(
            "Recompute Debt/Credit Balances",
            icon=ft.Icons.SYNC,
            on_click=self._handle_recompute_debt_credit_balances,
        )

        self.controls = [
            ft.Container(height=40),
            year_section,
            ft.Container(height=20),
            theme_switch,
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
