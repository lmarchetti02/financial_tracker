"""Implementation of the review dialog for expenses captured on the iPhone."""

from collections.abc import Callable
from dataclasses import dataclass
from logging import getLogger

import flet as ft

import database as db
from _helpers.constants import (DEFAULT_PROFILE_NAME, ICLOUD_DIRECTORY,
                                INBOX_IMPORTED_FILE_NAME,
                                INBOX_REJECTED_FILE_NAME, MONTHS)
from _helpers.expression_parser import evaluate_expression
from _helpers.inbox import (InboxEntry, append_archive, ensure_inbox_file,
                            export_lookups, read_inbox, stamp_imported,
                            write_inbox)

from .common import show_alert

logger = getLogger("financial_tracker")

# prefix marking the synthetic "create this category" dropdown option, so it can't collide with
# a real category name (which the lookup editor restricts to plain text)
_ADD_OPTION_PREFIX = "\x00add:"


@dataclass
class _PendingRow:
    """One reviewable entry: the parsed line plus the controls editing it.

    A plain mutable dataclass rather than a `:class:DataContainer` - this is transient widget
    state, not something that gets persisted.
    """

    entry: InboxEntry
    amount_field: ft.TextField
    category_picker: ft.Dropdown
    description_field: ft.TextField
    profile_picker: ft.Dropdown
    discarded: bool = False


def sync_lookups_for_phone() -> None:
    """Prepares the folder shared with the phone: the lookup exports and an empty inbox.

    Running this once is all the Shortcut needs to work - it reads the two exports for its
    pickers, and appends to the inbox this seeds.
    """
    logger.info("Called 'sync_lookups_for_phone'")

    export_lookups(ICLOUD_DIRECTORY, db.fetch_categories(), db.list_profiles())
    ensure_inbox_file(ICLOUD_DIRECTORY)


def review_inbox(page: ft.Page, on_imported: Callable[[], None] | None = None) -> bool:
    """Shows the review dialog if the phone captured anything since the last import.

    Unparseable lines are moved straight out to the rejected archive, so a mis-edited Shortcut
    can't wedge the dialog on every launch. A completely empty inbox is a silent no-op.

    Args:
        page (ft.Page): The page object.
        on_imported (Callable[[], None] | None): Called after rows were actually written, so the
            caller can refresh whatever is on screen. Defaults to `None`.

    Returns:
        bool: Whether there was anything pending to review.
    """
    logger.info("Called 'review_inbox'")

    entries, malformed = read_inbox(ICLOUD_DIRECTORY)

    if malformed:
        logger.debug(f"Moving {len(malformed)} malformed lines out of the inbox.")
        append_archive(ICLOUD_DIRECTORY, INBOX_REJECTED_FILE_NAME, malformed)
        write_inbox(ICLOUD_DIRECTORY, [entry.raw for entry in entries])

    if not entries:
        logger.debug("Nothing pending in the phone inbox.")
        return False

    InboxReviewDialog(page, entries, on_imported).show()
    return True


class InboxReviewDialog:
    """Encapsulates the review of the expenses waiting in the phone inbox.

    Nothing reaches a yearly database without passing through here: the phone can't see the
    category lookup list, so an entry carrying an unknown category is flagged and blocks the
    import until it's remapped (or the category is created on the spot).
    """

    def __init__(self, page: ft.Page, entries: list[InboxEntry], on_imported: Callable[[], None] | None) -> None:
        """Builds one reviewable row per pending entry."""
        self._page = page
        self._on_imported = on_imported
        self._categories = db.fetch_categories()
        self._profiles = db.list_profiles() or [DEFAULT_PROFILE_NAME]

        self._import_button = ft.Button("Import", icon=ft.Icons.DOWNLOAD, on_click=self._import_all)
        self._warning = ft.Text("", size=12, color=ft.Colors.ERROR, visible=False)
        self._rows = [self._build_row(entry) for entry in entries]
        self._rows_column = ft.Column(
            controls=[self._build_row_layout(row) for row in self._rows],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
            height=min(90 + 62 * len(self._rows), 420),
            width=780,
        )

        self._dialog = ft.AlertDialog(
            title=ft.Text(self._title()),
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Captured on your iPhone. Check each row before it's added to your books.",
                        size=12,
                        opacity=0.7,
                    ),
                    self._warning,
                    self._rows_column,
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Skip", on_click=self._skip),
                self._import_button,
            ],
        )

    def show(self) -> None:
        """Renders the dialog."""
        logger.info("Called 'show'")

        self._refresh_import_button()
        self._page.show_dialog(self._dialog)
        self._page.update()

    def _title(self) -> str:
        """Returns the dialog's title, reflecting how many entries are pending."""
        pending = self._active_rows()
        suffix = "expense" if len(pending) == 1 else "expenses"
        return f"{len(pending)} pending {suffix} from your iPhone"

    def _build_row(self, entry: InboxEntry) -> _PendingRow:
        """Builds the editable controls for one pending entry.

        Args:
            entry (`:class:InboxEntry`): The entry to render.

        Returns:
            `:class:_PendingRow`: The entry paired with its controls.
        """
        category_picker = ft.Dropdown(
            options=self._category_options(entry.category),
            value=entry.category if entry.category in self._categories else None,
            label="Category",
            width=190,
            error_text=None if entry.category in self._categories else f"'{entry.category}' is not a category",
        )

        row = _PendingRow(
            entry=entry,
            amount_field=ft.TextField(
                value=entry.cost_expression, label="Cost (€)", width=110, text_align=ft.TextAlign.RIGHT
            ),
            category_picker=category_picker,
            description_field=ft.TextField(value=entry.description, label="Description", expand=True),
            profile_picker=ft.Dropdown(
                options=[ft.DropdownOption(key=name, text=name) for name in self._profile_choices(entry.profile)],
                value=entry.profile,
                label="Profile",
                width=140,
            ),
        )

        # bound after construction, since the handler needs the row the picker belongs to
        category_picker.on_text_change = lambda _, row=row: self._handle_category_change(row)

        return row

    def _build_row_layout(self, row: _PendingRow) -> ft.Control:
        """Lays one pending row out, with its date on the left and a discard button on the right."""
        day = row.entry.day
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(f"{day.day} {MONTHS[day.month - 1]} {day.year}", size=12, no_wrap=True),
                    width=110,
                ),
                row.amount_field,
                row.category_picker,
                row.description_field,
                row.profile_picker,
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Discard this entry",
                    on_click=lambda e, row=row: self._discard(row),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        )

    def _category_options(self, category: str) -> list[ft.DropdownOption]:
        """Builds the category options, offering to create `category` when it's unknown.

        Args:
            category (str): The category the phone sent.

        Returns:
            list[ft.DropdownOption]: Every known category, plus a "create this one" entry when
                `category` isn't among them.
        """
        options = [ft.DropdownOption(key=name, text=name) for name in self._categories]

        if category and category not in self._categories:
            options.append(
                ft.DropdownOption(key=f"{_ADD_OPTION_PREFIX}{category}", text=f"+ Add '{category}' as new category")
            )

        return options

    def _profile_choices(self, profile: str) -> list[str]:
        """Returns the profile options, including `profile` itself if it has no data yet."""
        if profile and profile not in self._profiles:
            return [*self._profiles, profile]

        return self._profiles

    def _active_rows(self) -> list[_PendingRow]:
        """Returns the rows that haven't been discarded."""
        return [row for row in self._rows if not row.discarded]

    def _unresolved_rows(self) -> list[_PendingRow]:
        """Returns the rows still carrying a category that isn't in the lookup list."""
        return [row for row in self._active_rows() if row.category_picker.value not in self._categories]

    def _handle_category_change(self, row: _PendingRow) -> None:
        """Creates the category if the 'add' option was picked, then re-checks the import button.

        Args:
            row (`:class:_PendingRow`): The row whose category picker changed.
        """
        logger.info("Called '_handle_category_change'")

        picker = row.category_picker
        value = picker.value or ""

        if value.startswith(_ADD_OPTION_PREFIX):
            name = value.removeprefix(_ADD_OPTION_PREFIX)
            try:
                db.add_lookup_option(db.LookupKind.CATEGORIES, name)
            except ValueError as error:
                picker.value = None
                show_alert(self._page, "Cannot add category", str(error))
                self._refresh_import_button()
                return

            logger.debug(f"Added category '{name}' from the inbox review.")
            self._categories = db.fetch_categories()
            self._resync_category_pickers(name)

        picker.error_text = None
        self._refresh_import_button()

    def _resync_category_pickers(self, added: str) -> None:
        """Rebuilds every category dropdown after a new category was created.

        Args:
            added (str): The category that was just created, selected on any row that sent it.
        """
        for row in self._rows:
            selected = row.category_picker.value or ""
            if selected.startswith(_ADD_OPTION_PREFIX):
                selected = selected.removeprefix(_ADD_OPTION_PREFIX)

            row.category_picker.options = self._category_options(row.entry.category)
            row.category_picker.value = selected if selected in self._categories else None
            if row.category_picker.value is not None:
                row.category_picker.error_text = None

        logger.debug(f"Re-synced the category pickers around '{added}'.")

    def _discard(self, row: _PendingRow) -> None:
        """Marks a row as discarded, removing it from the dialog.

        Args:
            row (`:class:_PendingRow`): The row to drop.
        """
        logger.info("Called '_discard'")

        row.discarded = True
        self._rows_column.controls = [self._build_row_layout(r) for r in self._active_rows()]
        self._dialog.title = ft.Text(self._title())

        if not self._active_rows():
            logger.debug("Every pending entry was discarded.")
            self._commit([], self._discarded_lines())
            return

        self._refresh_import_button()
        self._page.update()

    def _refresh_import_button(self) -> None:
        """Disables the import button while any row's category is still unresolved."""
        unresolved = self._unresolved_rows()
        self._import_button.disabled = bool(unresolved)
        self._warning.value = (
            f"{len(unresolved)} entry's category isn't in your list yet - pick one to continue."
            if len(unresolved) == 1
            else f"{len(unresolved)} entries have categories that aren't in your list yet - pick one for each."
        )
        self._warning.visible = bool(unresolved)

    def _import_all(self, _: ft.Event) -> None:
        """Validates every row, then writes them all into their target year and profile."""
        logger.info("Called '_import_all'")

        rows = self._active_rows()
        prepared: list[tuple[db.DbLocation, db.Expense]] = []
        for row in rows:
            entry = self._prepare(row)
            if entry is None:
                return
            prepared.append(entry)

        # everything validated, so the writes can't stop half way and leave the inbox
        # disagreeing with what actually landed in the databases
        for location, expense in prepared:
            for which in db.WhichDb:
                db.initialize_db(location, which)
            db.add_item(location, expense)
            logger.debug(f"Imported a phone expense into {location}:\n{expense}")

        self._commit([stamp_imported(row.entry.raw) for row in rows], self._discarded_lines())

    def _prepare(self, row: _PendingRow) -> tuple[db.DbLocation, db.Expense] | None:
        """Turns one reviewed row into the expense to write and the database to write it to.

        Args:
            row (`:class:_PendingRow`): The row to convert.

        Returns:
            tuple[`:class:DbLocation`, `:class:Expense`] | None: The target location and the
                expense, or `None` if the row is invalid (already surfaced to the user).
        """
        raw_cost = row.amount_field.value or ""
        try:
            cost = evaluate_expression(raw_cost)
        except ValueError as error:
            show_alert(self._page, "Invalid cost", str(error))
            return None

        try:
            expense = db.Expense(
                month=row.entry.day.month,
                day_start=row.entry.day.day,
                day_end=None,
                description=row.description_field.value or "",
                category=row.category_picker.value,
                cost=cost,
                cost_expression=raw_cost,
            )
        except Exception as error:
            logger.debug(f"Rejected a reviewed inbox row: {error}", exc_info=True)
            show_alert(self._page, "Invalid expense", "Every entry needs a category and a cost greater than zero.")
            return None

        # the entry's own date picks the year, so a New Year's Eve expense imported in January
        # still lands in the right book, whichever year happens to be open
        return db.DbLocation(row.entry.day.year, row.profile_picker.value), expense

    def _discarded_lines(self) -> list[str]:
        """Returns the raw lines of every row the user dropped."""
        return [row.entry.raw for row in self._rows if row.discarded]

    def _commit(self, imported: list[str], discarded: list[str]) -> None:
        """Archives what was handled, empties the inbox, and closes the dialog.

        Args:
            imported (list[str]): The raw lines that were written to a database.
            discarded (list[str]): The raw lines the user dropped without importing.
        """
        logger.info("Called '_commit'")

        append_archive(ICLOUD_DIRECTORY, INBOX_IMPORTED_FILE_NAME, imported)
        append_archive(ICLOUD_DIRECTORY, INBOX_REJECTED_FILE_NAME, discarded)
        write_inbox(ICLOUD_DIRECTORY, [])

        self._page.pop_dialog()
        self._page.update()

        if imported and self._on_imported is not None:
            self._on_imported()

    def _skip(self, _: ft.Event) -> None:
        """Closes the dialog, leaving every pending entry where it is.

        Skipping is deliberately lossless: an entry stays in the inbox until it's imported or
        explicitly discarded, so it comes back at the next launch instead of disappearing.
        """
        logger.info("Called '_skip'")

        self._page.pop_dialog()
        self._page.update()
