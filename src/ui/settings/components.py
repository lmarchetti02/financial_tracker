"""Shared building blocks for the settings panels."""

import flet as ft


def setting_row(title: str, subtitle: str, control: ft.Control) -> ft.Container:
    """Builds one settings entry: a label and description on the left, its control on the right.

    Args:
        title (str): The setting's name.
        subtitle (str): A one-line description of what the setting does.
        control (ft.Control): The switch/button/field the user interacts with.

    Returns:
        ft.Container: The padded row.
    """
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(title, weight=ft.FontWeight.BOLD, size=15),
                        ft.Text(subtitle, size=12, opacity=0.7),
                    ],
                    spacing=2,
                    expand=True,
                ),
                control,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(left=18, top=14, right=18, bottom=14),
    )


def settings_card(rows: list[ft.Control]) -> ft.Card:
    """Groups `rows` into one card, separated by dividers.

    Args:
        rows (list[ft.Control]): The `:func:setting_row` entries to group.

    Returns:
        ft.Card: The card holding every row.
    """
    separated: list[ft.Control] = []
    for row in rows:
        if separated:
            separated.append(ft.Divider(height=1, thickness=1))
        separated.append(row)

    return ft.Card(content=ft.Column(controls=separated, spacing=0))


def panel_title(title: str, subtitle: str) -> ft.Column:
    """Builds the heading shown at the top of a settings panel."""
    return ft.Column(
        controls=[
            ft.Text(title, size=24, weight=ft.FontWeight.BOLD),
            ft.Text(subtitle, size=13, opacity=0.7),
        ],
        spacing=2,
    )
