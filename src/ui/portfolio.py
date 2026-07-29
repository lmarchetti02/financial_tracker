"""Implementation of the portfolio layout."""

from dataclasses import replace
from logging import getLogger

import flet as ft
from flet_datatable2 import DataColumn2, DataColumnSize

import database as db
from _helpers.formatting import enum_label, format_amount, parse_amount

from .common import build_styled_data_table, current_db_location, show_alert

logger = getLogger("financial_tracker")

_HEADING_COLOR = "#00695C"

_KIND_OPTIONS = [
    ft.DropdownOption(key=str(kind.value), text=enum_label(kind))
    for kind in sorted(db.HoldingKind, key=lambda k: k.name)
]
_REPLICATION_OPTIONS = [
    ft.DropdownOption(key=str(method.value), text=enum_label(method))
    for method in sorted(db.ReplicationMethod, key=lambda m: m.name)
]
_DISTRIBUTION_OPTIONS = [
    ft.DropdownOption(key=str(policy.value), text=enum_label(policy))
    for policy in sorted(db.DistributionPolicy, key=lambda p: p.name)
]


class PortfolioView(ft.Column):
    """Encapsulates the portfolio view: manage holdings and refresh their live prices."""

    def __init__(self, page: ft.Page) -> None:
        """Initializes the view, state variables, and layout."""
        super().__init__()
        logger.info("Called 'PortfolioView.__init__'")
        self._page = page

        self.location = current_db_location(page)

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self._init_controls()
        self.controls = self._build_layout()
        self.refresh()

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        self.name_text = ft.TextField(label="Name", width=300)
        self.ticker_text = ft.TextField(label="Ticker", width=110)
        self.kind_dropdown = ft.Dropdown(label="Type", options=_KIND_OPTIONS, width=170)
        self.issuer_text = ft.TextField(label="Issuer", width=160)
        self.region_text = ft.TextField(label="Region", width=300)
        self.currency_text = ft.TextField(label="Currency", width=120)
        self.replication_dropdown = ft.Dropdown(label="Replication", options=_REPLICATION_OPTIONS, width=230)
        self.distribution_dropdown = ft.Dropdown(label="Distribution", options=_DISTRIBUTION_OPTIONS, width=230)
        self.ter_text = ft.TextField(label="TER (%)", width=120)
        self.notes_text = ft.TextField(label="Notes", width=660, multiline=True)
        self.add_button = ft.Button("Add Holding", on_click=self.add_holding)
        self.clear_button = ft.Button("Clear Fields", on_click=self._handle_clear_click)

        self.refresh_prices_button = ft.Button(
            "Refresh Prices", icon=ft.Icons.REFRESH, color=_HEADING_COLOR, on_click=self.refresh_prices
        )
        self.holdings_table_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout, matching the other CRUD pages."""
        upper_row = ft.Row(
            controls=[
                self.name_text,
                ft.Container(width=20),
                self.ticker_text,
                ft.Container(width=20),
                self.kind_dropdown,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        issuer_row = ft.Row(
            controls=[
                self.issuer_text,
                ft.Container(width=20),
                self.region_text,
                ft.Container(width=20),
                self.currency_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        fund_details_row = ft.Row(
            controls=[
                self.replication_dropdown,
                ft.Container(width=20),
                self.distribution_dropdown,
                ft.Container(width=20),
                self.ter_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return [
            ft.Text("Portfolio", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=40),
            upper_row,
            fund_details_row,
            issuer_row,
            self.notes_text,
            ft.Row([self.add_button, self.clear_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            self.holdings_table_container,
            ft.Row([self.refresh_prices_button], alignment=ft.MainAxisAlignment.CENTER),
        ]

    def clear_inputs(self) -> None:
        """Clears the add-holding input controls."""
        self.name_text.value = ""
        self.ticker_text.value = ""
        self.kind_dropdown.value = None
        self.issuer_text.value = ""
        self.currency_text.value = ""
        self.region_text.value = ""
        self.replication_dropdown.value = None
        self.distribution_dropdown.value = None
        self.ter_text.value = ""
        self.notes_text.value = ""

    def _handle_clear_click(self, _: ft.Event) -> None:
        """Clears the add-holding inputs, resets the add button, and pushes the change to the page."""
        self.clear_inputs()
        self.reset_add_button()
        self._page.update()

    def _holding_fields_from_inputs(self, exclude_id: int | None = None) -> dict | None:
        """Validates the add/edit inputs and returns the fields they represent, or `None` if invalid.

        Deliberately excludes `quantity`/`last_price`/`last_price_updated`, since those aren't on
        this form (quantity is edited inline in the table, price is only ever set by a refresh) -
        callers apply the returned fields on top of a fresh or existing `:class:Holding` as needed.

        Args:
            exclude_id (int | None): A holding id to exclude from the duplicate-name check, so
                editing a holding doesn't collide with its own (unchanged) name. Defaults to `None`.
        """
        name = (self.name_text.value or "").strip()
        ticker = (self.ticker_text.value or "").strip()
        issuer = (self.issuer_text.value or "").strip()
        currency = (self.currency_text.value or "").strip()

        if not name:
            show_alert(self._page, "Missing name", "You must give the holding a name.")
            return None
        if not ticker:
            show_alert(self._page, "Missing ticker", "You must give the holding a ticker.")
            return None
        if self.kind_dropdown.value is None:
            show_alert(self._page, "Missing type", "You must choose a type for the holding.")
            return None
        if not issuer:
            show_alert(self._page, "Missing issuer", "You must give the holding an issuer.")
            return None
        if not currency:
            show_alert(self._page, "Missing currency", "You must give the holding a currency.")
            return None

        existing_names = {holding.name.lower() for hid, holding in self.holdings if hid != exclude_id}
        if name.lower() in existing_names:
            show_alert(self._page, "Duplicate holding", f"A holding named '{name}' already exists.")
            return None

        try:
            ter = self._parse_optional_ter(self.ter_text.value)
        except ValueError:
            show_alert(self._page, "Invalid TER", "The TER must be a real number (comma for decimals allowed).")
            return None

        return {
            "name": name,
            "ticker": ticker,
            "kind": db.HoldingKind(int(self.kind_dropdown.value)),
            "issuer": issuer,
            "currency": currency,
            "region": (self.region_text.value or "").strip() or None,
            "replication": db.ReplicationMethod(int(self.replication_dropdown.value))
            if self.replication_dropdown.value
            else None,
            "distribution": db.DistributionPolicy(int(self.distribution_dropdown.value))
            if self.distribution_dropdown.value
            else None,
            "notes": (self.notes_text.value or "").strip() or None,
            "ter": ter,
        }

    @staticmethod
    def _parse_optional_ter(raw: str | None) -> float | None:
        """Parses the TER field, treating a blank value as `None`."""
        raw = (raw or "").strip()
        return parse_amount(raw) if raw else None

    def add_holding(self, _: ft.Event) -> None:
        """Adds a new holding based on the user's inputs."""
        logger.info("Called 'add_holding'")

        fields = self._holding_fields_from_inputs()
        if fields is None:
            return

        holding = db.Holding(**fields)
        db.add_item(self.location, holding)
        logger.debug(f"Added holding:\n{holding}")

        self.clear_inputs()
        self.refresh()

    def delete_holding(self, e: ft.Event) -> None:
        """Deletes a holding after confirmation."""
        logger.info("Called 'delete_holding'")
        holding_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the holding."""
            db.remove_item(self.location, db.WhichDb.HOLDINGS, holding_id)
            self._page.pop_dialog()
            self.refresh()

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete holding"),
                content=ft.Text("Are you sure you want to delete this holding?"),
                actions=[
                    ft.TextButton("Yes", on_click=delete),
                    ft.TextButton("No", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def edit_holding(self, e: ft.Event) -> None:
        """Prefills the add-holding inputs from an existing holding, to edit it in place."""
        logger.info("Called 'edit_holding'")
        holding_id = e.control.data
        old_holding = next(h for hid, h in self.holdings if hid == holding_id)

        def modify(_: ft.Event) -> None:
            """Actually persists the edited holding."""
            fields = self._holding_fields_from_inputs(exclude_id=holding_id)
            if fields is None:
                return

            new_holding = replace(old_holding, **fields)
            if new_holding == old_holding:
                show_alert(self._page, "Unchanged holding", "You did not modify the holding.")
                return

            db.edit_item(self.location, holding_id, old_holding, new_holding)
            logger.debug(f"Edited holding {holding_id}:\n{new_holding}")

            self.clear_inputs()
            self.reset_add_button()
            self.refresh()

        self.add_button.content = "Edit Holding"
        self.add_button.color = ft.Colors.PURPLE
        self.add_button.on_click = modify

        self._fill_inputs_from_holding(old_holding)

    def reset_add_button(self) -> None:
        """Resets the add button to its base "Add Holding" state."""
        self.add_button.content = "Add Holding"
        self.add_button.color = None
        self.add_button.on_click = self.add_holding

    def _fill_inputs_from_holding(self, holding: db.Holding) -> None:
        """Populates the add-holding controls with an existing holding's values."""
        self.name_text.value = holding.name
        self.ticker_text.value = holding.ticker
        self.kind_dropdown.value = str(holding.kind.value)
        self.issuer_text.value = holding.issuer
        self.currency_text.value = holding.currency
        self.region_text.value = holding.region or ""
        self.replication_dropdown.value = str(holding.replication.value) if holding.replication is not None else None
        self.distribution_dropdown.value = str(holding.distribution.value) if holding.distribution is not None else None
        self.ter_text.value = format_amount(holding.ter, decimals=2) if holding.ter is not None else ""
        self.notes_text.value = holding.notes or ""

    def show_holding_info(self, e: ft.Event) -> None:
        """Shows every field of a holding, including the ones left out of the compact table."""
        logger.info("Called 'show_holding_info'")
        holding_id = e.control.data
        holding = next(h for hid, h in self.holdings if hid == holding_id)

        total = self._totals[holding_id]
        kind_total = self._kind_totals.get(holding.kind, 0.0)
        total_pct = (
            f"{format_amount(total / self._grand_total * 100, decimals=1)}%"
            if total is not None and self._grand_total
            else "—"
        )
        type_pct = (
            f"{format_amount(total / kind_total * 100, decimals=1)}%" if total is not None and kind_total else "—"
        )

        def info_row(label: str, value: str) -> ft.Row:
            """Builds one "label: value" line of the info dialog."""
            return ft.Row([ft.Text(label, weight=ft.FontWeight.BOLD, width=110), ft.Text(value)])

        rows = [
            info_row("Ticker", holding.ticker),
            info_row("Type", enum_label(holding.kind)),
            info_row("Issuer", holding.issuer),
            info_row("Currency", holding.currency),
            info_row("Region", holding.region or "—"),
            info_row("Replication", enum_label(holding.replication) if holding.replication is not None else "—"),
            info_row("Distribution", enum_label(holding.distribution) if holding.distribution is not None else "—"),
            info_row("Notes", holding.notes or "—"),
            info_row("TER (%)", f"{format_amount(holding.ter, decimals=2)}%" if holding.ter is not None else "—"),
            info_row("Price", f"€ {format_amount(holding.last_price)}" if holding.last_price is not None else "—"),
            info_row("Shares", format_amount(holding.quantity, decimals=3)),
            info_row("Total", f"€ {format_amount(total)}" if total is not None else "—"),
            info_row("Total (%)", total_pct),
            info_row("Type (%)", type_pct),
        ]

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(holding.name),
                content=ft.Column(controls=rows, tight=True, scroll=ft.ScrollMode.AUTO, width=380, height=420),
                actions=[ft.TextButton("Close", on_click=lambda _: self._page.pop_dialog())],
            )
        )

    def commit_quantity_cell(self, e: ft.Event) -> None:
        """Persists the number of shares/units for the holding whose cell was just edited."""
        logger.info("Called 'commit_quantity_cell'")
        holding_id = e.control.data
        holding = next(h for hid, h in self.holdings if hid == holding_id)
        raw_value = (e.control.value or "").strip()

        try:
            quantity = parse_amount(raw_value) if raw_value else 0.0
        except ValueError:
            show_alert(self._page, "Invalid quantity", "Shares must be a real number (comma for decimals allowed).")
            e.control.value = format_amount(holding.quantity, decimals=3)
            self._page.update()
            return

        if quantity < 0:
            show_alert(self._page, "Invalid quantity", "Shares can't be negative.")
            e.control.value = format_amount(holding.quantity, decimals=3)
            self._page.update()
            return

        db.edit_item(self.location, holding_id, holding, replace(holding, quantity=quantity))
        logger.debug(f"Saved quantity for holding {holding_id}: {quantity}")

        self.refresh()

    def refresh_prices(self, _: ft.Event) -> None:
        """Refreshes the live price of every holding, reporting any tickers that failed."""
        logger.info("Called 'refresh_prices'")

        failed_tickers = []
        for holding_id, holding in self.holdings:
            if db.refresh_holding_price(self.location, holding_id, holding) is None:
                failed_tickers.append(holding.ticker)

        self.refresh()

        if failed_tickers:
            show_alert(
                self._page,
                "Some prices couldn't be refreshed",
                f"Failed to fetch a price for: {', '.join(failed_tickers)}.",
            )

    def refresh(self) -> None:
        """Reloads the holdings, recomputes their totals, and rebuilds the table."""
        logger.info("Called 'refresh'")

        self.holdings = db.fetch_holdings(self.location)
        self._totals, self._grand_total, self._kind_totals, self._weighted_ter = self._compute_totals(self.holdings)
        self.holdings_table_container.controls = self._build_holdings_section()

        self._page.update()

    @staticmethod
    def _compute_totals(
        holdings: list[tuple[int, "db.Holding"]],
    ) -> tuple[dict[int, float | None], float, dict["db.HoldingKind", float], float | None]:
        """Computes each holding's market value, the portfolio grand total, per-kind totals, and blended TER."""
        totals = {
            holding_id: (holding.quantity * holding.last_price if holding.last_price is not None else None)
            for holding_id, holding in holdings
        }
        grand_total = sum(total for total in totals.values() if total is not None)

        kind_totals: dict[db.HoldingKind, float] = {}
        for holding_id, holding in holdings:
            total = totals[holding_id]
            if total is not None:
                kind_totals[holding.kind] = kind_totals.get(holding.kind, 0.0) + total

        # value-weighted average TER, across holdings that have both a TER and a known market value
        weighted_ter_sum = 0.0
        weighted_ter_total = 0.0
        for holding_id, holding in holdings:
            total = totals[holding_id]
            if holding.ter is not None and total is not None:
                weighted_ter_sum += holding.ter * total
                weighted_ter_total += total
        weighted_ter = weighted_ter_sum / weighted_ter_total if weighted_ter_total else None

        return totals, grand_total, kind_totals, weighted_ter

    def _build_holdings_section(self) -> list[ft.Control]:
        """Builds the portfolio summary line and the holdings table."""
        if not self.holdings:
            return [ft.Text("Add a holding above to start tracking your portfolio.")]

        summary_text = f"Total portfolio value: € {format_amount(self._grand_total)}"
        if self._weighted_ter is not None:
            summary_text += f"  •  Total TER: {format_amount(self._weighted_ter, decimals=2)}%"

        summary = ft.Text(summary_text, size=16, weight=ft.FontWeight.BOLD)
        return [summary, self._build_holdings_table()]

    def _build_holdings_table(self) -> ft.Control:
        """Builds the holdings `:class:DataTable2`, one row per holding, kept to the bare-minimum columns.

        Every other field (ticker, issuer, currency, region, replication, distribution, notes, price) is
        available from the info button rather than taking up table width, since the window can't be
        zoomed out like a spreadsheet to fit them all.
        """
        columns = [
            DataColumn2(label=ft.Text("Name"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("TER (%)"), numeric=True, fixed_width=90),
            DataColumn2(label=ft.Text("Shares"), numeric=True, fixed_width=120),
            DataColumn2(label=ft.Text("Total"), numeric=True, fixed_width=150),
            DataColumn2(label=ft.Text("Total (%)"), numeric=True, fixed_width=100),
            DataColumn2(label=ft.Text("Type (%)"), numeric=True, fixed_width=100),
            DataColumn2(label=ft.Text(""), fixed_width=190),
        ]

        rows = []
        for holding_id, holding in self.holdings:
            color = db.HOLDING_KIND_COLORS.get(holding.kind, "#000000")
            icon = db.HOLDING_KIND_ICONS.get(holding.kind, ft.Icons.HELP_OUTLINE)
            total = self._totals[holding_id]
            kind_total = self._kind_totals.get(holding.kind, 0.0)

            total_str = f"€ {format_amount(total)}" if total is not None else "—"
            total_pct = (
                f"{format_amount(total / self._grand_total * 100, decimals=1)}%"
                if total is not None and self._grand_total
                else "—"
            )
            type_pct = (
                f"{format_amount(total / kind_total * 100, decimals=1)}%" if total is not None and kind_total else "—"
            )

            cells = [
                ft.DataCell(
                    ft.Row(
                        controls=[ft.Icon(icon, color=color, size=18), ft.Text(holding.name)],
                        spacing=6,
                        tight=True,
                    )
                ),
                ft.DataCell(ft.Text(f"{format_amount(holding.ter, decimals=2)}%" if holding.ter is not None else "—")),
                ft.DataCell(
                    ft.TextField(
                        value=format_amount(holding.quantity, decimals=3),
                        text_align=ft.TextAlign.RIGHT,
                        text_size=14,
                        border=ft.InputBorder.NONE,
                        content_padding=6,
                        dense=True,
                        data=holding_id,
                        on_blur=self.commit_quantity_cell,
                        on_submit=self.commit_quantity_cell,
                    )
                ),
                ft.DataCell(ft.Text(total_str)),
                ft.DataCell(ft.Text(total_pct)),
                ft.DataCell(ft.Text(type_pct)),
                ft.DataCell(
                    ft.Row(
                        controls=[
                            ft.Button(
                                icon=ft.Icons.INFO_OUTLINE,
                                width=50,
                                height=30,
                                data=holding_id,
                                on_click=self.show_holding_info,
                            ),
                            ft.Button(
                                icon=ft.Icons.EDIT,
                                width=50,
                                height=30,
                                data=holding_id,
                                color=ft.Colors.BLUE,
                                on_click=self.edit_holding,
                            ),
                            ft.Button(
                                icon=ft.Icons.DELETE,
                                width=50,
                                height=30,
                                data=holding_id,
                                on_click=self.delete_holding,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                ),
            ]
            rows.append(ft.DataRow(cells=cells))

        return build_styled_data_table(columns, rows, _HEADING_COLOR)


def portfolio_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return PortfolioView(page)
