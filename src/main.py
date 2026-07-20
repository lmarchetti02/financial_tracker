"""The heart of the app."""

from logging import getLogger

import flet as ft

from _helpers import setup_logger
from _helpers.constants import APP_DIRECTORY
from database.db_operations import WhichDb, initialize_db
from ui.expenses import expenses_view
from ui.home import home_view
from ui.income import income_view
from ui.portfolio import portfolio_view
from ui.transfers import transfers_view
from ui.welcome import welcome_page

logger = getLogger("financial_tracker")


def startup_layout(page: ft.Page) -> None:
    """Renders the main page."""

    def menu_change(e: ft.Event) -> None:
        """Controls navigation between pages."""
        index = e.control.selected_index

        match index:
            case 0:
                main_content.content = home_view()
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
                main_content.content = portfolio_view()
                logger.debug("Net worth view selected")
            case _:
                return

        page.update()

    side_menu = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.HOME, label="Home"),
            ft.NavigationRailDestination(icon=ft.Icons.CREDIT_CARD_OUTLINED, label="Expenses"),
            ft.NavigationRailDestination(icon=ft.Icons.MONEY, label="Income"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Transfers"),
            ft.NavigationRailDestination(icon=ft.Icons.PIE_CHART, label="Net Worth"),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS, label="Settings"),
        ],
        on_change=menu_change,
    )

    main_content = ft.Container(content=home_view(), expand=True, padding=20)

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

    page.title = "Financial Tracker"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window.full_screen = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.RED, font_family="JetBrains Mono")

    def initialize_tracker(selected_year: int) -> None:
        logger.info("Called 'initialize_tracker'")

        # save selected year for current session
        page.session.store.set("selected_year", selected_year)

        # create data dir if it doesn't exist
        APP_DIRECTORY.mkdir(exist_ok=True, parents=True)

        # create db if it doesn't exists
        for db in WhichDb:
            initialize_db(selected_year, db)

        # start home
        startup_layout(page)
        page.update()

    welcome_page(page, initialize_tracker)


ft.run(main)
