"""Lock screen shown at startup when a password has been set."""

from collections.abc import Callable
from logging import getLogger

import flet as ft

import database as db

logger = getLogger("financial_tracker")

MAX_ATTEMPTS = 3


def lock_screen(page: ft.Page, on_unlock: Callable[[], None]) -> None:
    """Renders the lock screen, calling `on_unlock` once the correct password is typed.

    After `MAX_ATTEMPTS` wrong attempts the app window is closed. The counter only lives for as
    long as this screen does, so it resets on every launch.

    Args:
        page (ft.Page): The flet `Page` object.
        on_unlock (Callable[[], None]): A function taking no input and producing no output, called
            once the correct password has been typed.
    """
    logger.info("Called 'lock_screen'")

    attempts = 0

    async def unlock(_: ft.Event) -> None:
        """Checks the typed password, unlocking the app or counting down the remaining attempts."""
        nonlocal attempts

        if db.verify_app_password(password_field.value or ""):
            logger.debug("Correct password typed, unlocking.")
            page.controls.clear()
            page.update()
            on_unlock()
            return

        attempts += 1
        remaining = MAX_ATTEMPTS - attempts
        logger.debug(f"Wrong password typed, {remaining} attempt(s) left.")

        if remaining <= 0:
            await page.window.destroy()
            return

        password_field.value = ""
        password_field.error_text = f"Wrong password. {remaining} attempt(s) left."
        page.update()

    if page.height is None:
        raise RuntimeError("Cannot retrieve page height.")

    password_field = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        autofocus=True,
        width=300,
        on_submit=unlock,
    )

    layout = ft.Column(
        controls=[
            # title
            ft.Container(height=page.height * 0.1),
            ft.Text("FINANCIAL TRACKER", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("by Luca Marchetti", size=22),
            ft.Container(height=page.height * 0.2),
            # password prompt
            password_field,
            ft.Button("Unlock", on_click=unlock),
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    page.add(layout)
