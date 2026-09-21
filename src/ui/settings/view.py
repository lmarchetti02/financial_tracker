"""Implementation of the settings layout: a sidebar of panels, one group of settings each."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

import database as db

from ..common import current_db_location, show_alert
from .components import panel_title, setting_row, settings_card
from .lookup_editor import LookupListEditor
from .password import PasswordSettings

logger = getLogger("financial_tracker")


class SettingsView(ft.Row):
    """Encapsulates the settings view: a `:class:ft.NavigationRail` of panels beside their content.

    Adding a setting means adding a `:func:setting_row` to the relevant `_build_*_panel`; adding a
    whole group means one destination plus one more panel builder, with no other layout to touch.
    """

    def __init__(self, page: ft.Page, on_change_year: Callable[[ft.Event], None]) -> None:
        """Initializes the view on the 'General' panel."""
        super().__init__()
        self._page = page
        self._on_change_year = on_change_year
        self._password = PasswordSettings(page)

        self.expand = True
        self.vertical_alignment = ft.CrossAxisAlignment.STRETCH

        self._panels = [
            self._build_general_panel(),
            self._build_security_panel(),
            self._build_lists_panel(),
            self._build_maintenance_panel(),
        ]
        self._content = ft.Container(
            content=self._panels[0], expand=True, padding=ft.Padding(left=30, top=0, right=0, bottom=0)
        )

        self.controls = [
            ft.NavigationRail(
                selected_index=0,
                label_type=ft.NavigationRailLabelType.ALL,
                min_width=90,
                destinations=[
                    ft.NavigationRailDestination(icon=ft.Icons.TUNE, label="General"),
                    ft.NavigationRailDestination(icon=ft.Icons.LOCK_OUTLINE, label="Security"),
                    ft.NavigationRailDestination(icon=ft.Icons.LIST_ALT, label="Lists"),
                    ft.NavigationRailDestination(icon=ft.Icons.BUILD_OUTLINED, label="Maintenance"),
                ],
                on_change=self._handle_panel_change,
            ),
            ft.VerticalDivider(width=1),
            self._content,
        ]

    def _handle_panel_change(self, e: ft.Event) -> None:
        """Swaps the shown panel for the one picked in the sidebar."""
        logger.info("Called '_handle_panel_change'")

        self._content.content = self._panels[e.control.selected_index]
        self._page.update()

    def _build_general_panel(self) -> ft.Column:
        """Builds the 'General' panel: the open year/profile and the theme toggle."""
        location = current_db_location(self._page)

        return self._build_panel(
            "General",
            "Which dataset is open, and how the app looks.",
            [
                setting_row(
                    "Year and profile",
                    f"Currently open: {location.year} · {location.profile}",
                    ft.Button("Change Year/Profile", icon=ft.Icons.SWAP_HORIZ, on_click=self._on_change_year),
                ),
                setting_row(
                    "Dark theme",
                    "Use the dark color scheme. Remembered across launches.",
                    ft.Switch(
                        value=self._page.theme_mode == ft.ThemeMode.DARK,
                        on_change=self._handle_theme_change,
                    ),
                ),
            ],
        )

    def _build_security_panel(self) -> ft.Column:
        """Builds the 'Security' panel: the optional startup password."""
        return self._build_panel(
            "Security",
            "The optional password asked for at launch. It is global: one password for every year and profile.",
            [
                setting_row(
                    "Require password at startup",
                    "Ask for a password before the app opens. This is a convenience lock, not encryption — "
                    "the database files stay readable on disk.",
                    self._password.switch,
                ),
                setting_row(
                    "Change password",
                    "Replace the startup password. The current one is needed.",
                    self._password.change_button,
                ),
            ],
        )

    def _build_lists_panel(self) -> ft.Column:
        """Builds the 'Lists' panel: the editor for every user-editable lookup list."""
        return self._build_panel(
            "Lists",
            "The editable options behind the category, source, kind and region fields. "
            "Renaming an entry updates every year and profile that uses it.",
            [LookupListEditor(self._page)],
            scroll=False,
        )

    def _build_maintenance_panel(self) -> ft.Column:
        """Builds the 'Maintenance' panel: the cross-year data-repair actions."""
        return self._build_panel(
            "Maintenance",
            "Repair actions that run across every year and profile.",
            [
                setting_row(
                    "Recompute Debt/Credit balances",
                    "Rebuilds every Debt and Credit account's monthly balances from their transfers, in every "
                    "year and profile. Use it to fix drift, or to backfill accounts for older transfers.",
                    ft.Button(
                        "Recompute",
                        icon=ft.Icons.SYNC,
                        on_click=self._handle_recompute_debt_credit_balances,
                    ),
                ),
            ],
        )

    def _build_panel(self, title: str, subtitle: str, body: list[ft.Control], scroll: bool = True) -> ft.Column:
        """Assembles one panel from its heading and its rows.

        Args:
            title (str): The panel's name.
            subtitle (str): A short description of what the panel holds.
            body (list[ft.Control]): The `:func:setting_row` entries, grouped into one card, or a
                self-contained control shown as-is.
            scroll (bool): Whether the panel scrolls. `False` for a body that manages its own height.

        Returns:
            ft.Column: The assembled panel.
        """
        content = settings_card(body) if scroll else body[0]

        return ft.Column(
            controls=[panel_title(title, subtitle), content],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.AUTO if scroll else None,
        )

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
