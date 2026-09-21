"""Implementation of the generic lookup-list editor backing the settings 'Lists' panel."""

from logging import getLogger

import flet as ft

import database as db

from ..common import show_alert

logger = getLogger("financial_tracker")

# (tab label, singular noun used in the 'New ...' field, description of the field it backs)
_LOOKUP_LABELS: dict[db.LookupKind, tuple[str, str, str]] = {
    db.LookupKind.CATEGORIES: ("Categories", "category", "The categories an expense can be filed under."),
    db.LookupKind.SOURCES: ("Sources", "source", "Where a logged income can come from."),
    db.LookupKind.KINDS: ("Kinds", "kind", "The kinds a transfer can have."),
    db.LookupKind.REGIONS: ("Regions", "region", "The regions a holding's allocation can be split across."),
}


class LookupListEditor(ft.Column):
    """The 'Lists' panel: one editor reused for every `:enum:LookupKind`, picked with a segmented button.

    Adding a new lookup list needs nothing here beyond an entry in `_LOOKUP_LABELS` — the selector,
    the search box, the rows and the add field are all driven by the selected `:enum:LookupKind`.
    """

    def __init__(self, page: ft.Page) -> None:
        """Initializes the editor on the first lookup list."""
        super().__init__()
        self._page = page
        self._kind = next(iter(_LOOKUP_LABELS))
        self._search = ""

        self.expand = True
        self.spacing = 16

        self._selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value=kind.name, label=ft.Text(label))
                for kind, (label, _, _) in _LOOKUP_LABELS.items()
            ],
            selected=[self._kind.name],
            allow_empty_selection=False,
            allow_multiple_selection=False,
            on_change=self._handle_kind_change,
        )
        self._description = ft.Text(size=13, opacity=0.7)
        self._search_field = ft.TextField(
            label="Search",
            prefix_icon=ft.Icons.SEARCH,
            width=260,
            dense=True,
            on_change=self._handle_search_change,
        )
        self._new_name_field = ft.TextField(width=260, dense=True, on_submit=self._add_option)
        self._rows = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

        self.controls = [
            self._selector,
            self._description,
            ft.Row(
                controls=[
                    self._search_field,
                    ft.Row(
                        controls=[self._new_name_field, ft.Button("Add", icon=ft.Icons.ADD, on_click=self._add_option)],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(content=ft.Card(content=self._rows), expand=True),
        ]

        self._sync_to_kind()

    def _handle_kind_change(self, e: ft.Event) -> None:
        """Switches the editor to the lookup list picked in the segmented button."""
        logger.info("Called '_handle_kind_change'")

        self._kind = db.LookupKind[e.control.selected[0]]
        self._search = ""
        self._search_field.value = ""
        self._sync_to_kind()
        self._page.update()

    def _handle_search_change(self, e: ft.Event) -> None:
        """Filters the shown entries down to those containing the typed text."""
        self._search = (e.control.value or "").strip().lower()
        self._refresh_rows()
        self._page.update()

    def _sync_to_kind(self) -> None:
        """Re-labels the description and the add field for the selected list, then reloads its rows."""
        _, item_label, description = _LOOKUP_LABELS[self._kind]
        self._description.value = description
        self._new_name_field.label = f"New {item_label}"
        self._new_name_field.value = ""
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        """Rebuilds the displayed rows for the selected list from the database, honoring the search."""
        options = [o for o in db.fetch_lookup_options(self._kind) if self._search in o.name.lower()]

        if not options:
            message = "No entry matches the search." if self._search else "This list is empty."
            self._rows.controls = [ft.Container(content=ft.Text(message, opacity=0.6), padding=16)]
            return

        self._rows.controls = [self._build_row(option) for option in options]

    def _build_row(self, option: db.LookupOption) -> ft.Container:
        """Builds a single entry row with its rename/delete buttons."""
        tooltip = "Required by the app" if option.is_system else None

        name = ft.Row(
            controls=[ft.Text(option.name, size=14, expand=True)],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if option.is_system:
            name.controls.insert(0, ft.Icon(ft.Icons.LOCK_OUTLINE, size=14, opacity=0.6, tooltip=tooltip))

        return ft.Container(
            content=ft.Row(
                controls=[
                    name,
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        icon_size=18,
                        disabled=option.is_system,
                        tooltip=tooltip or "Rename",
                        on_click=lambda _: self._rename_option(option.name),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        icon_size=18,
                        disabled=option.is_system,
                        tooltip=tooltip or "Delete",
                        on_click=lambda _: self._delete_option(option.name),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=18, top=0, right=8, bottom=0),
        )

    def _add_option(self, _: ft.Event) -> None:
        """Adds the entry typed into the 'New ...' field to the selected list."""
        logger.info("Called '_add_option'")

        try:
            db.add_lookup_option(self._kind, self._new_name_field.value or "")
        except ValueError as error:
            show_alert(self._page, "Cannot add", str(error))
            return

        self._new_name_field.value = ""
        self._refresh_rows()
        self._page.update()

    def _rename_option(self, old_name: str) -> None:
        """Shows a dialog to rename an entry."""
        logger.info("Called '_rename_option'")

        name_field = ft.TextField(label="Name", value=old_name, autofocus=True)

        def save(_: ft.Event) -> None:
            """Applies the rename, if valid."""
            try:
                db.rename_lookup_option(self._kind, old_name, name_field.value or "")
            except ValueError as error:
                show_alert(self._page, "Cannot rename", str(error))

            self._page.pop_dialog()
            self._refresh_rows()
            self._page.update()

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

    def _delete_option(self, name: str) -> None:
        """Shows a confirmation dialog, then deletes the entry if it's safe to do so."""
        logger.info("Called '_delete_option'")

        def delete(_: ft.Event) -> None:
            """Actually deletes the entry."""
            success = db.delete_lookup_option(self._kind, name)
            if not success:
                show_alert(
                    self._page,
                    "Cannot delete",
                    f"'{name}' is required by the app or still used by existing data, so it cannot be deleted.",
                )

            self._page.pop_dialog()
            self._refresh_rows()
            self._page.update()

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
