"""Implementation of the portfolio layout."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from logging import getLogger
from typing import ClassVar

import flet as ft
import flet_charts as fch
from flet_datatable2 import DataColumn2, DataColumnSize

import database as db
from _helpers.expression_parser import evaluate_expression
from _helpers.formatting import enum_label, format_amount, parse_amount
from plotting import (build_kind_allocation_pie,
                      show_detailed_region_diversification,
                      show_portfolio_diversification)

from .common import (CollapsibleFormMixin, build_styled_data_table,
                     current_db_location, show_alert)

logger = getLogger("financial_tracker")

_HEADING_COLOR = "#00695C"
_CHART_ASPECT_RATIO = 5 / 7
_LOCK_COLUMN_WIDTH = 70
_DELTA_COLUMN_WIDTH = 170

_REBALANCE_CAPTION = (
    "Buy/sell amounts assume rebalancing within your current portfolio value - not new "
    "deposits or withdrawals - so every buy is matched by an equal sell."
)
_CONTRIBUTION_CAPTION = (
    "Amounts show how to invest your new money across the underweight kinds so the portfolio "
    "moves toward target without selling anything. Locked kinds never receive any of it."
)

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


class PortfolioView(CollapsibleFormMixin, ft.Column):
    """Encapsulates the portfolio view: manage holdings and refresh their live prices.

    Holdings are split into two independent sections: "Long Term Assets" (open-ended holdings,
    with no `maturity_date`) and "Fixed Term Assets" (a defined maturity date, e.g. an individual
    bond or a target-maturity ETF like an iBonds series). Both sections share a single add/edit
    form; which one a holding lands in is decided purely by whether a maturity date was entered.
    """

    _item_label: ClassVar[str] = "Holding"
    _form_height: ClassVar[int] = 330

    def __init__(self, page: ft.Page) -> None:
        """Initializes the view, state variables, and layout."""
        super().__init__()
        logger.info("Called 'PortfolioView.__init__'")
        self._page = page

        self.location = current_db_location(page)
        self.long_term_kind_filter: db.HoldingKind | None = None
        self.fixed_term_kind_filter: db.HoldingKind | None = None
        self.long_term_sort_ascending: bool | None = None
        self.fixed_term_sort_ascending: bool | None = None

        self.expand = True
        self.alignment = ft.MainAxisAlignment.START
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self._init_controls()
        self._init_collapsible_form()
        self.controls = self._build_layout()
        self.refresh()

    def _init_controls(self) -> None:
        """Instantiates all Flet controls used in the view."""
        self.name_text = ft.TextField(label="Name", width=450)
        self.ticker_text = ft.TextField(label="Ticker", width=170)
        self.kind_dropdown = ft.Dropdown(
            label="Type", options=_KIND_OPTIONS, width=280, on_select=self._handle_kind_change
        )
        self.maturity_date_text = ft.TextField(label="Maturity Date (YYYY-MM-DD)", width=340, disabled=True)
        self.replication_dropdown = ft.Dropdown(label="Replication", options=_REPLICATION_OPTIONS, width=230)
        self.distribution_dropdown = ft.Dropdown(label="Distribution", options=_DISTRIBUTION_OPTIONS, width=230)
        self.ter_text = ft.TextField(label="TER (%)", width=120)
        self.issuer_text = ft.TextField(label="Issuer", width=230)
        self.region_text = ft.TextField(label="Region", width=230)
        self.currency_text = ft.TextField(label="Currency", width=120)
        self.notes_text = ft.TextField(label="Notes", width=660, multiline=True)
        self.add_button = ft.Button("Add Holding", on_click=self.add_holding)
        self.clear_button = ft.Button("Clear Fields", on_click=self._handle_clear_click)

        self.long_term_refresh_prices_button = ft.Button(
            "Refresh Prices",
            icon=ft.Icons.REFRESH,
            color=_HEADING_COLOR,
            on_click=lambda _: self.refresh_prices(self.long_term_holdings),
        )
        self.fixed_term_refresh_prices_button = ft.Button(
            "Refresh Prices",
            icon=ft.Icons.REFRESH,
            color=_HEADING_COLOR,
            on_click=lambda _: self.refresh_prices(self.fixed_term_holdings),
        )
        self.diversification_button = ft.Button(
            "Show Diversification",
            icon=ft.Icons.PIE_CHART_OUTLINE,
            color=_HEADING_COLOR,
            on_click=lambda _: show_portfolio_diversification(self._page),
        )
        self.detailed_diversification_button = ft.Button(
            "Detailed Diversification",
            icon=ft.Icons.TRAVEL_EXPLORE,
            color=_HEADING_COLOR,
            on_click=lambda _: show_detailed_region_diversification(self._page),
        )
        self.asset_allocation_button = ft.Button(
            "Asset Allocation",
            icon=ft.Icons.DONUT_LARGE,
            color=_HEADING_COLOR,
            on_click=self.show_asset_allocation,
        )
        self.long_term_table_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        self.fixed_term_table_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        self.long_term_kind_filter_menu = self._build_kind_filter_menu(self.filter_long_term_kind)
        self.fixed_term_kind_filter_menu = self._build_kind_filter_menu(self.filter_fixed_term_kind)

        # collapsible form
        upper_row = ft.Row(
            controls=[self.name_text, ft.Container(width=20), self.ticker_text],
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

        maturity_row = ft.Row(
            controls=[self.kind_dropdown, ft.Container(width=20), self.maturity_date_text],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.form_content = ft.Column(
            controls=[
                upper_row,
                maturity_row,
                fund_details_row,
                issuer_row,
                self.notes_text,
                ft.Row([self.add_button, self.clear_button], alignment=ft.MainAxisAlignment.CENTER),
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _build_layout(self) -> list[ft.Control]:
        """Assembles the initialized controls into the final layout, matching the other CRUD pages."""
        return [
            ft.Text("Portfolio", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=5),
            ft.Row([self.toggle_form_button], alignment=ft.MainAxisAlignment.CENTER),
            self.form_container,
            ft.Container(height=5),
            ft.Text("Long Term Assets", size=20, weight=ft.FontWeight.BOLD, color=_HEADING_COLOR),
            self.long_term_table_container,
            ft.Row(
                [self.diversification_button, self.detailed_diversification_button, self.asset_allocation_button],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=20),
            ft.Text("Fixed Term Assets", size=20, weight=ft.FontWeight.BOLD, color=_HEADING_COLOR),
            self.fixed_term_table_container,
        ]

    def clear_inputs(self) -> None:
        """Clears the add-holding input controls."""
        self.name_text.value = ""
        self.ticker_text.value = ""
        self.kind_dropdown.value = None
        self.issuer_text.value = ""
        self.region_text.value = ""
        self.currency_text.value = ""
        self.replication_dropdown.value = None
        self.distribution_dropdown.value = None
        self.ter_text.value = ""
        self.maturity_date_text.value = ""
        self.maturity_date_text.disabled = True
        self.notes_text.value = ""

    def _handle_kind_change(self, _: ft.Event) -> None:
        """Enables the maturity field only for a Fixed Maturity Bond, clearing it for every other type."""
        logger.info("Called '_handle_kind_change'")
        is_fixed_maturity_bond = self.kind_dropdown.value == str(db.HoldingKind.FIXED_MATURITY_BOND.value)
        if not is_fixed_maturity_bond:
            self.maturity_date_text.value = ""
        self.maturity_date_text.disabled = not is_fixed_maturity_bond
        self._page.update()

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
        kind = db.HoldingKind(int(self.kind_dropdown.value))
        if not issuer:
            show_alert(self._page, "Missing issuer", "You must give the holding an issuer.")
            return None
        if not currency:
            show_alert(self._page, "Missing currency", "You must give the holding a currency.")
            return None

        existing_names = {holding.name.lower() for hid, holding in self._holdings_by_id.items() if hid != exclude_id}
        if name.lower() in existing_names:
            show_alert(self._page, "Duplicate holding", f"A holding named '{name}' already exists.")
            return None

        try:
            ter = self._parse_optional_ter(self.ter_text.value)
        except ValueError:
            show_alert(self._page, "Invalid TER", "The TER must be a real number (comma for decimals allowed).")
            return None

        try:
            maturity_date = self._parse_optional_maturity_date(self.maturity_date_text.value)
        except ValueError:
            show_alert(
                self._page,
                "Invalid maturity date",
                "The maturity date must be a valid date in YYYY-MM-DD format.",
            )
            return None

        if kind == db.HoldingKind.FIXED_MATURITY_BOND and maturity_date is None:
            show_alert(
                self._page,
                "Missing maturity date",
                "You must set a maturity date for a fixed-maturity bond.",
            )
            return None

        return {
            "name": name,
            "ticker": ticker,
            "kind": kind,
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
            "maturity_date": maturity_date,
        }

    @staticmethod
    def _parse_optional_ter(raw: str | None) -> float | None:
        """Parses the TER field, treating a blank value as `None`."""
        raw = (raw or "").strip()
        return parse_amount(raw) if raw else None

    @staticmethod
    def _parse_optional_maturity_date(raw: str | None) -> str | None:
        """Parses the maturity date field, treating a blank value as `None` (a long-term holding)."""
        raw = (raw or "").strip()
        return date.fromisoformat(raw).isoformat() if raw else None

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
        self._set_form_expanded(False)
        self.refresh()

    def delete_holding(self, e: ft.Event) -> None:
        """Deletes a holding after confirmation."""
        logger.info("Called 'delete_holding'")
        holding_id = e.control.data

        def delete(_: ft.Event) -> None:
            """Actually deletes the holding."""
            db.delete_holding(self.location, holding_id)
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
        old_holding = self._holdings_by_id[holding_id]

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
            self._set_form_expanded(False)
            self.refresh()

        self.add_button.content = "Edit Holding"
        self.add_button.color = ft.Colors.PURPLE
        self.add_button.on_click = modify

        self._set_form_expanded(True)
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
        self.region_text.value = holding.region or ""
        self.currency_text.value = holding.currency
        self.replication_dropdown.value = str(holding.replication.value) if holding.replication is not None else None
        self.distribution_dropdown.value = str(holding.distribution.value) if holding.distribution is not None else None
        self.ter_text.value = format_amount(holding.ter, decimals=2) if holding.ter is not None else ""
        self.maturity_date_text.value = holding.maturity_date or ""
        self.maturity_date_text.disabled = holding.kind != db.HoldingKind.FIXED_MATURITY_BOND
        self.notes_text.value = holding.notes or ""

    def show_holding_info(self, e: ft.Event) -> None:
        """Shows every field of a holding, including the ones left out of the compact table."""
        logger.info("Called 'show_holding_info'")
        holding_id = e.control.data
        holding = self._holdings_by_id[holding_id]

        if db.is_fixed_term(holding):
            totals, kind_totals, grand_total = (
                self._fixed_term_totals,
                self._fixed_term_kind_totals,
                self._fixed_term_grand_total,
            )
        else:
            totals, kind_totals, grand_total = (
                self._long_term_totals,
                self._long_term_kind_totals,
                self._long_term_grand_total,
            )

        total = totals[holding_id]
        kind_total = kind_totals.get(holding.kind, 0.0)
        total_pct = (
            f"{format_amount(total / grand_total * 100, decimals=1)}%" if total is not None and grand_total else "—"
        )
        type_pct = (
            f"{format_amount(total / kind_total * 100, decimals=1)}%" if total is not None and kind_total else "—"
        )
        region_summary = self._region_allocation_summary(holding_id)

        def info_row(label: str, value: str) -> ft.Row:
            """Builds one "label: value" line of the info dialog."""
            return ft.Row(
                [ft.Text(label, weight=ft.FontWeight.BOLD, width=110), ft.Text(value, expand=True)],
                vertical_alignment=ft.CrossAxisAlignment.START,
            )

        rows = [
            info_row("Ticker", holding.ticker),
            info_row("Type", enum_label(holding.kind)),
            info_row("Issuer", holding.issuer),
            info_row("Currency", holding.currency),
            info_row("Region", holding.region or "—"),
            info_row("Detailed Regions", region_summary),
            info_row("Replication", enum_label(holding.replication) if holding.replication is not None else "—"),
            info_row("Distribution", enum_label(holding.distribution) if holding.distribution is not None else "—"),
            info_row("Maturity Date", holding.maturity_date or "—"),
            info_row("Notes", holding.notes or "—"),
            info_row("TER (%)", f"{format_amount(holding.ter, decimals=2)}%" if holding.ter is not None else "—"),
            info_row("Price", f"€ {format_amount(holding.last_price)}" if holding.last_price is not None else "—"),
            info_row("Shares", format_amount(holding.quantity, decimals=3)),
            info_row("Total", f"€ {format_amount(total)}" if total is not None else "—"),
            info_row("Total (%)", total_pct),
            info_row("Type (%)", type_pct),
        ]

        expired = db.is_expired(holding)
        title_text = f"{holding.name} (EXPIRED)" if expired else holding.name

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    title_text,
                    width=380,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    color=ft.Colors.RED if expired else None,
                ),
                content=ft.Column(controls=rows, tight=True, scroll=ft.ScrollMode.AUTO, width=380, height=430),
                actions=[ft.TextButton("Close", on_click=lambda _: self._page.pop_dialog())],
            )
        )

    def _region_allocation_summary(self, holding_id: int) -> str:
        """Builds a human-readable summary of a holding's region breakdown, e.g. "Europe 60.0%, Unallocated 40.0%"."""
        allocations = self.region_allocations.get(holding_id, {})
        if not allocations:
            return "—"

        allocated_pct = sum(allocations.values())
        remainder = max(0.0, 100.0 - allocated_pct)

        parts = [f"{region} {format_amount(pct, decimals=1)}%" for region, pct in sorted(allocations.items())]
        if remainder > 0:
            parts.append(f"Unallocated {format_amount(remainder, decimals=1)}%")

        return ", ".join(parts)

    def edit_region_allocations(self, e: ft.Event) -> None:
        """Opens a dialog to enter/edit a holding's regional-exposure percentage breakdown."""
        logger.info("Called 'edit_region_allocations'")
        holding_id = e.control.data
        holding = self._holdings_by_id[holding_id]

        regions = db.fetch_regions()
        if not regions:
            show_alert(self._page, "No regions configured", "There are no detailed regions configured yet.")
            return

        existing = self.region_allocations.get(holding_id, {})
        total_text = ft.Text(f"Total: {format_amount(sum(existing.values()), decimals=2)}%", weight=ft.FontWeight.BOLD)

        def update_total(_: ft.Event) -> None:
            """Recomputes and displays the sum of every entered percentage."""
            total = 0.0
            for field in region_fields.values():
                raw_value = (field.value or "").strip()
                if not raw_value:
                    continue
                try:
                    total += parse_amount(raw_value)
                except ValueError:
                    continue

            total_text.value = f"Total: {format_amount(total, decimals=2)}%"
            self._page.update()

        region_fields = {
            region: ft.TextField(
                label=region,
                value=format_amount(existing[region], decimals=2) if region in existing else "",
                width=220,
                suffix="%",
                on_change=update_total,
            )
            for region in regions
        }

        def save(_: ft.Event) -> None:
            """Validates and persists the entered breakdown."""
            allocations: dict[str, float] = {}
            total = 0.0
            for region, field in region_fields.items():
                raw_value = (field.value or "").strip()
                if not raw_value:
                    continue

                try:
                    percentage = parse_amount(raw_value)
                except ValueError:
                    show_alert(self._page, "Invalid percentage", f"'{region}' must be a real number.")
                    return
                if not (0 < percentage <= 100):
                    show_alert(self._page, "Invalid percentage", f"'{region}' must be between 0 and 100.")
                    return

                allocations[region] = percentage
                total += percentage

            if total > 100.0001:
                show_alert(self._page, "Allocation exceeds 100%", "The entered percentages add up to more than 100%.")
                return

            db.save_region_allocations(self.location, holding_id, allocations)
            logger.debug(f"Saved region allocations for holding {holding_id}:\n{allocations}")

            self._page.pop_dialog()
            self.refresh()

        fields = list(region_fields.values())
        midpoint = (len(fields) + 1) // 2
        columns = ft.Row(
            controls=[  # type: ignore
                ft.Column(controls=fields[:midpoint], tight=True),  # type: ignore
                ft.Column(controls=fields[midpoint:], tight=True),  # type: ignore
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=20,
        )

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Detailed Regions — {holding.name}", width=420, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
                ),
                content=ft.Column(
                    controls=[
                        total_text,
                        ft.Column(
                            controls=[ft.Container(columns, padding=ft.Padding(left=0, top=10, right=0, bottom=0))],
                            tight=True,
                            scroll=ft.ScrollMode.AUTO,
                            height=430,
                        ),
                    ],
                    tight=True,
                    width=460,
                ),
                actions=[
                    ft.TextButton("Save", on_click=save),
                    ft.TextButton("Cancel", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def show_asset_allocation(self, _: ft.Event) -> None:
        """Opens a dialog with the long-term portfolio's current allocation by `:enum:HoldingKind` and a target form.

        Shows a pie chart of the current allocation alongside an editable form to set a target %
        per kind, live-updating how much to buy/sell in each asset class to reach it. Totals are
        recomputed from every long-term holding regardless of `self.long_term_kind_filter`, since
        both the chart and the rebalancing calculation must always be long-term-portfolio-wide.
        Fixed-term holdings are excluded entirely, since they're held to maturity rather than
        rebalanced.
        """
        logger.info("Called 'show_asset_allocation'")

        if self._page.width is None or self._page.height is None:
            raise RuntimeError("Cannot retrieve the page size.")

        all_holdings = [(hid, h) for hid, h in db.fetch_holdings(self.location) if not db.is_fixed_term(h)]
        _, grand_total, kind_totals, _ = self._compute_totals(all_holdings)  # type: ignore

        if not grand_total:
            show_alert(
                self._page,
                "No priced long-term holdings yet",
                "Add and price some long-term holdings before viewing the asset allocation.",
            )
            return

        dialog_width = self._page.width * 0.9
        dialog_height = self._page.height * 0.9
        rows_height = dialog_height - 50
        chart_width = rows_height * _CHART_ASPECT_RATIO

        chart = fch.MatplotlibChart(
            figure=build_kind_allocation_pie(kind_totals),
            expand=True,
            align=ft.Alignment.CENTER,
        )

        existing = db.fetch_kind_targets(self.location)
        # a Fixed Maturity Bond always carries a maturity date, so it's always excluded from
        # `all_holdings` above - it could never have a long-term total to rebalance towards
        kinds = sorted(
            (kind for kind in db.HoldingKind if kind is not db.HoldingKind.FIXED_MATURITY_BOND),
            key=lambda k: k.name,
        )
        current_pcts = {kind: kind_totals.get(kind, 0.0) / grand_total * 100 for kind in kinds}

        total_text = ft.Text(
            f"Target total: {format_amount(sum(existing.values()), decimals=2)}%", weight=ft.FontWeight.BOLD
        )
        delta_texts = {kind: ft.Text("—", size=12) for kind in kinds}
        unallocated_text = ft.Text("", size=12, color=ft.Colors.GREY)

        def _set_kind_label(kind: db.HoldingKind, resulting_pct: float | None) -> None:
            """Updates a kind field's label with its current %, and projected new % once known."""
            base = f"{enum_label(kind)} (current {format_amount(current_pcts[kind], decimals=2)}%"
            if resulting_pct is None:
                kind_fields[kind].label = f"{base})"
            else:
                kind_fields[kind].label = f"{base} → {format_amount(resulting_pct, decimals=2)}%)"

        def _parsed_target_percentages() -> dict[db.HoldingKind, float]:
            """Parses every kind's currently entered target percentage, skipping blank/invalid ones."""
            targets: dict[db.HoldingKind, float] = {}
            for kind in kinds:
                raw_value = (kind_fields[kind].value or "").strip()
                if not raw_value:
                    continue
                try:
                    targets[kind] = evaluate_expression(raw_value)
                except ValueError:
                    continue
            return targets

        def update_deltas() -> None:
            """Recomputes and displays the buy/sell (or buy-only, in contribution mode) amount per kind."""
            try:
                contribution = evaluate_expression((contribution_field.value or "").strip())
            except ValueError:
                contribution = 0.0

            if contribution <= 0:
                unallocated_text.value = ""
                caption.value = _REBALANCE_CAPTION
                for kind in kinds:
                    if lock_checkboxes[kind].value:
                        # locked kinds are left untouched by definition - always exactly balanced,
                        # regardless of any rounding in the displayed current-percentage value
                        delta_texts[kind].value = "Balanced"
                        delta_texts[kind].color = None
                        _set_kind_label(kind, current_pcts[kind])
                        continue

                    raw_value = (kind_fields[kind].value or "").strip()
                    try:
                        target_pct = evaluate_expression(raw_value) if raw_value else 0.0
                    except ValueError:
                        delta_texts[kind].value = "—"
                        delta_texts[kind].color = None
                        _set_kind_label(kind, None)
                        continue

                    delta = target_pct / 100 * grand_total - kind_totals.get(kind, 0.0)
                    if abs(delta) < 0.005:
                        delta_texts[kind].value = "Balanced"
                        delta_texts[kind].color = None
                    elif delta > 0:
                        delta_texts[kind].value = f"Buy € {format_amount(delta)}"
                        delta_texts[kind].color = ft.Colors.GREEN
                    else:
                        delta_texts[kind].value = f"Sell € {format_amount(abs(delta))}"
                        delta_texts[kind].color = ft.Colors.RED
                    _set_kind_label(kind, target_pct)
                return

            # contribution mode: only ever buy, never sell, and locked kinds never receive any of it
            caption.value = _CONTRIBUTION_CAPTION
            new_total = grand_total + contribution
            target_pcts = _parsed_target_percentages()
            unlocked = [kind for kind in kinds if not lock_checkboxes[kind].value]

            raw_needed = {
                kind: max(0.0, target_pcts[kind] / 100 * new_total - kind_totals.get(kind, 0.0))
                for kind in unlocked
                if kind in target_pcts
            }
            total_needed = sum(raw_needed.values())

            allocation: dict[db.HoldingKind, float] = {}
            if total_needed <= contribution:
                leftover = contribution - total_needed
                total_unlocked_pct = sum(target_pcts.get(kind, 0.0) for kind in unlocked)
                for kind in raw_needed:
                    share = target_pcts[kind] / total_unlocked_pct * leftover if total_unlocked_pct else 0.0
                    allocation[kind] = raw_needed[kind] + share
            else:
                for kind, needed in raw_needed.items():
                    allocation[kind] = needed / total_needed * contribution

            for kind in kinds:
                if lock_checkboxes[kind].value or kind not in allocation:
                    delta_texts[kind].value = "Balanced"
                    delta_texts[kind].color = None
                    _set_kind_label(kind, kind_totals.get(kind, 0.0) / new_total * 100)
                    continue

                amount = allocation[kind]
                if amount < 0.005:
                    delta_texts[kind].value = "Balanced"
                    delta_texts[kind].color = None
                else:
                    delta_texts[kind].value = f"Buy € {format_amount(amount)}"
                    delta_texts[kind].color = ft.Colors.GREEN
                _set_kind_label(kind, (kind_totals.get(kind, 0.0) + amount) / new_total * 100)

            unallocated = contribution - sum(allocation.values())
            unallocated_text.value = f"Unallocated: € {format_amount(unallocated)}" if unallocated > 0.005 else ""

        def update_total(_: ft.Event) -> None:
            """Recomputes and displays the sum of every entered target percentage."""
            total = sum(_parsed_target_percentages().values())

            total_text.value = f"Target total: {format_amount(total, decimals=2)}%"
            update_deltas()
            self._page.update()

        kind_fields = {
            kind: ft.TextField(
                label=f"{enum_label(kind)} (current {format_amount(current_pcts[kind], decimals=2)}%)",
                value=format_amount(existing[kind], decimals=2) if kind in existing else "",
                width=400,
                suffix="%",
                on_change=update_total,
            )
            for kind in kinds
        }

        locked_previous_values: dict[db.HoldingKind, str] = {}

        def toggle_lock(e: ft.Event, kind: db.HoldingKind) -> None:
            """Locks/unlocks a kind's target field to its current allocation percentage."""
            field = kind_fields[kind]
            if e.control.value:
                locked_previous_values[kind] = field.value or ""
                field.value = format_amount(current_pcts[kind], decimals=2)
                field.read_only = True
            else:
                field.value = locked_previous_values.pop(kind, "")
                field.read_only = False
            update_total(e)

        lock_checkboxes = {
            kind: ft.Checkbox(
                tooltip=f"Lock {enum_label(kind)} to its current allocation",
                on_change=lambda e, kind=kind: toggle_lock(e, kind),
            )
            for kind in kinds
        }

        contribution_field = ft.TextField(
            label="New money to invest (€)",
            width=400,
            suffix="€",
            on_change=update_total,
        )
        caption = ft.Text(_REBALANCE_CAPTION, size=12, color=ft.Colors.GREY)

        update_deltas()

        def save(_: ft.Event) -> None:
            """Validates and persists the entered target allocation."""
            targets: dict[db.HoldingKind, float] = {}
            total = 0.0
            for kind, field in kind_fields.items():
                raw_value = (field.value or "").strip()
                if not raw_value:
                    continue

                try:
                    percentage = evaluate_expression(raw_value)
                except ValueError:
                    show_alert(
                        self._page,
                        "Invalid percentage",
                        f"'{enum_label(kind)}' must be a real number or arithmetic expression (comma for "
                        "decimals allowed).",
                    )
                    return
                if percentage == 0:
                    # a zero target (typed, or locked to a currently-empty kind) is the same as unset
                    continue
                if not (0 < percentage <= 100):
                    show_alert(self._page, "Invalid percentage", f"'{enum_label(kind)}' must be between 0 and 100.")
                    return

                targets[kind] = percentage
                total += percentage

            if abs(total - 100.0) > 0.05:
                show_alert(
                    self._page,
                    "Target must total 100%",
                    f"The entered percentages add up to {format_amount(total, decimals=2)}%, not 100%.",
                )
                return

            db.save_kind_targets(self.location, targets)
            logger.debug(f"Saved kind targets:\n{targets}")

            self._page.pop_dialog()

        header_row = ft.Row(
            [
                ft.Container(width=400),
                ft.Container(width=30),
                ft.Container(
                    ft.Text("Lock", size=12, weight=ft.FontWeight.BOLD),
                    width=_LOCK_COLUMN_WIDTH,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(width=8),
                ft.Container(width=_DELTA_COLUMN_WIDTH),
            ],
            spacing=0,
        )
        rows = [
            ft.Row(
                [
                    kind_fields[kind],
                    ft.Container(width=30),
                    ft.Container(lock_checkboxes[kind], width=_LOCK_COLUMN_WIDTH, alignment=ft.Alignment.CENTER),
                    ft.Container(width=8),
                    ft.Container(delta_texts[kind], width=_DELTA_COLUMN_WIDTH, alignment=ft.Alignment.CENTER_RIGHT),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            for kind in kinds
        ]

        self._page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Asset Allocation"),
                content=ft.Row(
                    controls=[
                        ft.Container(  # type: ignore
                            ft.Container(chart, width=chart_width, height=rows_height),
                            expand=9,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            controls=[  # type: ignore
                                total_text,
                                contribution_field,
                                unallocated_text,
                                ft.Container(height=10),
                                header_row,
                                ft.Column(controls=rows, tight=True, spacing=15),
                                ft.Container(height=10),
                                caption,
                            ],
                            tight=True,
                            expand=10,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    width=dialog_width,
                    spacing=30,
                ),
                actions=[
                    ft.TextButton("Save", on_click=save),
                    ft.TextButton("Cancel", on_click=lambda _: self._page.pop_dialog()),
                ],
            )
        )

    def commit_quantity_cell(self, e: ft.Event) -> None:
        """Persists the number of shares/units for the holding whose cell was just edited."""
        logger.info("Called 'commit_quantity_cell'")
        holding_id = e.control.data
        holding = self._holdings_by_id[holding_id]
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

    def refresh_prices(self, holdings: list[tuple[int, "db.Holding"]]) -> None:
        """Refreshes the live price of every given holding, reporting any tickers that failed."""
        logger.info("Called 'refresh_prices'")

        failed_tickers = []
        for holding_id, holding in holdings:
            if db.refresh_holding_price(self.location, holding_id, holding) is None:
                failed_tickers.append(holding.ticker)

        self.refresh()

        if failed_tickers:
            show_alert(
                self._page,
                "Some prices couldn't be refreshed",
                f"Failed to fetch a price for: {', '.join(failed_tickers)}.",
            )

    @staticmethod
    def _build_kind_filter_menu(on_click: Callable[[ft.Event], None]) -> ft.PopupMenuButton:
        """Builds a "Filter by type" popup menu for a holdings table."""
        return ft.PopupMenuButton(
            icon=ft.Icons.FILTER_ALT,
            icon_color=_HEADING_COLOR,
            icon_size=20,
            padding=0,
            menu_padding=0,
            tooltip="Filter by type",
            items=[
                ft.PopupMenuItem(enum_label(kind), data=kind, on_click=on_click)
                for kind in sorted(db.HoldingKind, key=lambda k: k.name)
            ]
            + [ft.PopupMenuItem()]
            + [ft.PopupMenuItem("Clear Filter", data=None, on_click=on_click)],
        )

    def filter_long_term_kind(self, e: ft.Event) -> None:
        """Filters the long-term holdings table down to one `:enum:HoldingKind`, or clears the filter."""
        logger.info("Called 'filter_long_term_kind'")
        self.long_term_kind_filter = e.control.data
        self.refresh()

    def filter_fixed_term_kind(self, e: ft.Event) -> None:
        """Filters the fixed-term holdings table down to one `:enum:HoldingKind`, or clears the filter."""
        logger.info("Called 'filter_fixed_term_kind'")
        self.fixed_term_kind_filter = e.control.data
        self.refresh()

    def sort_long_term_by_total(self, e: ft.DataColumnSortEvent) -> None:
        """Sorts the long-term holdings table by market value (the "Total" column)."""
        logger.info("Called 'sort_long_term_by_total'")
        self.long_term_sort_ascending = e.ascending
        self.refresh()

    def sort_fixed_term_by_total(self, e: ft.DataColumnSortEvent) -> None:
        """Sorts the fixed-term holdings table by market value (the "Total" column)."""
        logger.info("Called 'sort_fixed_term_by_total'")
        self.fixed_term_sort_ascending = e.ascending
        self.refresh()

    def refresh(self) -> None:
        """Reloads the holdings, splits them into long-/fixed-term groups, and rebuilds both tables."""
        logger.info("Called 'refresh'")

        all_holdings = db.fetch_holdings(self.location)
        self._holdings_by_id: dict[int, db.Holding] = dict(all_holdings)
        self.region_allocations = db.fetch_region_allocations(self.location)

        (
            self.long_term_holdings,
            self._long_term_totals,
            self._long_term_grand_total,
            self._long_term_kind_totals,
            self._long_term_weighted_ter,
        ) = self._prepare_group(
            [(hid, h) for hid, h in all_holdings if not db.is_fixed_term(h)],
            self.long_term_kind_filter,
            self.long_term_sort_ascending,
        )
        (
            self.fixed_term_holdings,
            self._fixed_term_totals,
            self._fixed_term_grand_total,
            self._fixed_term_kind_totals,
            self._fixed_term_weighted_ter,
        ) = self._prepare_group(
            [(hid, h) for hid, h in all_holdings if db.is_fixed_term(h)],
            self.fixed_term_kind_filter,
            self.fixed_term_sort_ascending,
        )

        self.long_term_table_container.controls = self._build_holdings_section(
            holdings=self.long_term_holdings,
            totals=self._long_term_totals,
            kind_totals=self._long_term_kind_totals,
            grand_total=self._long_term_grand_total,
            weighted_ter=self._long_term_weighted_ter,
            kind_filter_menu=self.long_term_kind_filter_menu,
            refresh_button=self.long_term_refresh_prices_button,
            sort_ascending=self.long_term_sort_ascending,
            sort_handler=self.sort_long_term_by_total,
            show_maturity_column=False,
            empty_message="Add a holding above to start tracking your long-term portfolio.",
        )
        self.fixed_term_table_container.controls = self._build_holdings_section(
            holdings=self.fixed_term_holdings,
            totals=self._fixed_term_totals,
            kind_totals=self._fixed_term_kind_totals,
            grand_total=self._fixed_term_grand_total,
            weighted_ter=self._fixed_term_weighted_ter,
            kind_filter_menu=self.fixed_term_kind_filter_menu,
            refresh_button=self.fixed_term_refresh_prices_button,
            sort_ascending=self.fixed_term_sort_ascending,
            sort_handler=self.sort_fixed_term_by_total,
            show_maturity_column=True,
            empty_message="Add a holding above with a Maturity Date (e.g. a bond or an iBonds-style ETF) to "
            "track it here.",
        )

        self._page.update()

    def _prepare_group(
        self,
        holdings: list[tuple[int, "db.Holding"]],
        kind_filter: db.HoldingKind | None,
        sort_ascending: bool | None,
    ) -> tuple[
        list[tuple[int, "db.Holding"]], dict[int, float | None], float, dict["db.HoldingKind", float], float | None
    ]:
        """Filters one group's holdings by kind, computes its totals, and sorts it by value if requested."""
        if kind_filter is not None:
            holdings = [(hid, h) for hid, h in holdings if h.kind == kind_filter]

        totals, grand_total, kind_totals, weighted_ter = self._compute_totals(holdings)

        if sort_ascending is not None:
            holdings = sorted(holdings, key=lambda item: self._total_sort_key(item[0], totals, sort_ascending))

        return holdings, totals, grand_total, kind_totals, weighted_ter

    @staticmethod
    def _total_sort_key(holding_id: int, totals: dict[int, float | None], sort_ascending: bool) -> tuple[bool, float]:
        """Sort key for a holdings list by market value, always placing unpriced holdings last."""
        total = totals[holding_id]
        if total is None:
            return True, 0.0
        return False, total if sort_ascending else -total

    @staticmethod
    def _compute_totals(
        holdings: list[tuple[int, "db.Holding"]],
    ) -> tuple[dict[int, float | None], float, dict["db.HoldingKind", float], float | None]:
        """Computes each holding's market value, the group's grand total, per-kind totals, and blended TER."""
        totals = {holding_id: db.compute_holding_value(holding) for holding_id, holding in holdings}
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

    def _build_holdings_section(
        self,
        *,
        holdings: list[tuple[int, "db.Holding"]],
        totals: dict[int, float | None],
        kind_totals: dict["db.HoldingKind", float],
        grand_total: float,
        weighted_ter: float | None,
        kind_filter_menu: ft.PopupMenuButton,
        refresh_button: ft.Button,
        sort_ascending: bool | None,
        sort_handler: Callable[[ft.DataColumnSortEvent], None],
        show_maturity_column: bool,
        empty_message: str,
    ) -> list[ft.Control]:
        """Builds one group's summary line and holdings table."""
        if not holdings:
            return [ft.Text(empty_message)]

        summary_text = f"Total value: € {format_amount(grand_total)}"
        if weighted_ter is not None:
            summary_text += f"  •  Total TER: {format_amount(weighted_ter, decimals=2)}%"

        summary = ft.Text(summary_text, size=16, weight=ft.FontWeight.BOLD)
        header_row = ft.Row(
            [summary, ft.Row([kind_filter_menu, refresh_button])],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        table = self._build_holdings_table(
            holdings, totals, kind_totals, grand_total, sort_ascending, sort_handler, show_maturity_column
        )
        return [header_row, table]

    def _build_holdings_table(
        self,
        holdings: list[tuple[int, "db.Holding"]],
        totals: dict[int, float | None],
        kind_totals: dict["db.HoldingKind", float],
        grand_total: float,
        sort_ascending: bool | None,
        sort_handler: Callable[[ft.DataColumnSortEvent], None],
        show_maturity_column: bool,
    ) -> ft.Control:
        """Builds one group's holdings `:class:DataTable2`, one row per holding, kept to the bare-minimum columns.

        Every other field (ticker, issuer, currency, region, replication, distribution, notes, price) is
        available from the info button rather than taking up table width, since the window can't be
        zoomed out like a spreadsheet to fit them all.
        """
        total_column_index = 3
        columns = [
            DataColumn2(label=ft.Text("Name"), size=DataColumnSize.S),
            DataColumn2(label=ft.Text("TER (%)"), numeric=True, fixed_width=90),
            DataColumn2(label=ft.Text("Shares"), numeric=True, fixed_width=120),
            DataColumn2(label=ft.Text("Total"), numeric=True, fixed_width=150, on_sort=sort_handler),
            DataColumn2(label=ft.Text("Total (%)"), numeric=True, fixed_width=100),
            DataColumn2(label=ft.Text("Type (%)"), numeric=True, fixed_width=100),
        ]
        if show_maturity_column:
            columns.append(DataColumn2(label=ft.Text("Maturity"), fixed_width=120))
        columns.append(DataColumn2(label=ft.Text(""), fixed_width=240))

        rows = []
        for holding_id, holding in holdings:
            color = db.HOLDING_KIND_COLORS.get(holding.kind, "#000000")
            icon = db.HOLDING_KIND_ICONS.get(holding.kind, ft.Icons.HELP_OUTLINE)
            total = totals[holding_id]
            kind_total = kind_totals.get(holding.kind, 0.0)

            total_str = f"€ {format_amount(total)}" if total is not None else "—"
            total_pct = (
                f"{format_amount(total / grand_total * 100, decimals=1)}%" if total is not None and grand_total else "—"
            )
            type_pct = (
                f"{format_amount(total / kind_total * 100, decimals=1)}%" if total is not None and kind_total else "—"
            )

            expired = db.is_expired(holding)
            name_text = f"{holding.name} (EXPIRED)" if expired else holding.name

            cells = [
                ft.DataCell(
                    ft.Row(
                        controls=[
                            ft.Icon(icon, color=color, size=18),
                            ft.Text(name_text, color=ft.Colors.RED if expired else None),
                        ],
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
                        border_width=0,
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
            ]
            if show_maturity_column:
                cells.append(ft.DataCell(ft.Text(holding.maturity_date)))

            action_buttons = [
                ft.Button(
                    icon=ft.Icons.INFO_OUTLINE,
                    width=50,
                    height=30,
                    data=holding_id,
                    on_click=self.show_holding_info,
                ),
            ]
            if not show_maturity_column:
                # region allocation only makes sense for a diversified, long-term holding - a
                # fixed-term one is dropped from the diversification tools entirely (see
                # `show_portfolio_diversification`/`show_detailed_region_diversification`)
                action_buttons.append(
                    ft.Button(
                        icon=ft.Icons.PUBLIC,
                        width=50,
                        height=30,
                        data=holding_id,
                        color=_HEADING_COLOR,
                        tooltip="Detailed Regions",
                        on_click=self.edit_region_allocations,
                    )
                )
            action_buttons += [
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
            ]
            cells.append(ft.DataCell(ft.Row(controls=action_buttons, alignment=ft.MainAxisAlignment.CENTER)))
            rows.append(ft.DataRow(cells=cells))

        table = build_styled_data_table(columns, rows, _HEADING_COLOR)
        if sort_ascending is not None:
            table.sort_column_index = total_column_index
            table.sort_ascending = sort_ascending
        return table


def portfolio_view(page: ft.Page) -> ft.Control:
    """Wrapper function to instantiate and return the class-based view."""
    return PortfolioView(page)
