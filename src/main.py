"""The heart of the app."""

from logging import getLogger

import flet as ft

from _helpers import setup_logger
from _helpers.constants import APP_DIRECTORY
from database.db_operations import (WhichDb, get_theme_preference,
                                    initialize_config_db, initialize_db,
                                    seed_accounts_for_new_year)
from ui.accounts import accounts_view
from ui.expenses import expenses_view
from ui.home import home_view
from ui.income import income_view
from ui.settings import settings_view
from ui.transfers import transfers_view
from ui.welcome import welcome_page

logger = getLogger("financial_tracker")


def initialize_tracker(page: ft.Page, selected_year: int) -> None:
    """Prepares the databases for `selected_year` and renders the main layout."""
    logger.info("Called 'initialize_tracker'")

    # save selected year for current session
    page.session.store.set("selected_year", selected_year)

    # create data dir if it doesn't exist
    APP_DIRECTORY.mkdir(exist_ok=True, parents=True)

    # create db if it doesn't exists
    for db in WhichDb:
        initialize_db(selected_year, db)

    # carry over accounts (not balances) from the most recent prior year, if any
    seed_accounts_for_new_year(selected_year)

    # start home
    startup_layout(page)
    page.update()


def startup_layout(page: ft.Page) -> None:
    """Renders the main page."""

    def menu_change(e: ft.Event) -> None:
        """Controls navigation between pages."""
        index = e.control.selected_index

        match index:
            case 0:
                main_content.content = home_view(page)
                logger.debug("Home view selected")
            case 1:
                main_content.content = expenses_view(page)
                logger.debug("Add expense view selected")
            case 2:
                main_content.content = income_view(page)
                logger.debug("Income view selected")
            case 3:
                main_content.content = transfers_view(page)
                logger.debug("Transfers view selected")
            case 4:
                main_content.content = accounts_view(page)
                logger.debug("Accounts view selected")
            case 5:
                main_content.content = settings_view(page, go_to_welcome)
                logger.debug("Settings view selected")
            case _:
                main_content.content = ft.Text("Work in progress...")

        page.update()

    def go_to_welcome(_: ft.Event) -> None:
        """Wipes the page and returns to the welcome/year-selection screen."""
        page.controls.clear()
        page.update()
        welcome_page(page, lambda year: initialize_tracker(page, year))

    side_menu = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.HOME, label="Home"),
            ft.NavigationRailDestination(icon=ft.Icons.CREDIT_CARD_OUTLINED, label="Expenses"),
            ft.NavigationRailDestination(icon=ft.Icons.MONEY, label="Income"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Transfers"),
            ft.NavigationRailDestination(icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED, label="Accounts"),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS, label="Settings"),
        ],
        on_change=menu_change,
    )

    main_content = ft.Container(content=home_view(page), expand=True, padding=20)

    home_layout = ft.Row(
        controls=[
            side_menu,
            ft.VerticalDivider(width=1),
            main_content,
        ],
        expand=True,
    )

    page.add(home_layout)


def main(page: ft.Page):
    """Entry point of the application."""
    setup_logger()
    initialize_config_db()

    page.title = "Financial Tracker"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window.full_screen = True
    page.theme_mode = ft.ThemeMode.DARK if get_theme_preference() == "dark" else ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.RED, font_family="JetBrains Mono")

    welcome_page(page, lambda year: initialize_tracker(page, year))


ft.run(main)
