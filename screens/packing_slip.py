import flet as ft
import uuid
import os
import json
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update
from core.pdf_gen import pdf_engine, print_pdf


class PackingSlipTab(ft.Column):
    """
    Packing Slip — pulls Pending orders for a party, lets user set pack qty
    (0..available), saves packing_slip + packing_slip_items, updates order status.
    """

    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        self._pending_items   = []   # list of row-data dicts
        self._all_items_meta  = {}
        self._party_gst_rate  = 5.0
        self._party_tax_type  = "GST"

        # ── Header ───────────────────────────────────────────
        S = AppStyles.get_input_style()
        self.slip_no   = ft.TextField(label="Slip No",   width=130, **S)
        self.slip_date = ft.TextField(label="Date",      width=130, value=date.today().isoformat(), **S)
        self.party_dd  = ft.Dropdown(label="Select Party *", width=280, on_change=self.on_party_change, **S)
        self.agent_dd  = ft.Dropdown(label="Agent",      width=180, **S)
        self.trans_dd  = ft.Dropdown(label="Transporter",width=200, **S)
        self.dest      = ft.TextField(label="Destination",width=160, **S)
        self.cases     = ft.TextField(label="No of Cases",width=100, value="0", keyboard_type=ft.KeyboardType.NUMBER, **S)
        self.prepared  = ft.TextField(label="Prepared By",width=140, **S)
        self.checked   = ft.TextField(label="Checked By", width=140, **S)
        self.packed_by = ft.TextField(label="Packed By",  width=140, **S)

        # ── Header fields ────────────────────────────────────
        self.party_order_no = ft.TextField(label="Party Order No", width=140, **S)
        self.party_order_dt = ft.TextField(label="Party Order Dt", width=140, value=date.today().isoformat(), **S)
        self.order_by       = ft.TextField(label="Order By",       width=140, **S)
        self.order_thro     = ft.Dropdown(label="Order Thro'",     width=140, value="DIRECT", options=[ft.dropdown.Option("DIRECT"), ft.dropdown.Option("AGENT")], **S)
        self.docs_by        = ft.RadioGroup(content=ft.Row([
            ft.Text("Docs By:", size=12, weight="bold"),
            ft.Radio(value="Direct", label="Direct"),
            ft.Radio(value="Bank",   label="Bank"),
        ], spacing=10), value="Direct")
        self.compliments    = ft.TextField(label="Compliments",    width=280, **S)
        self.qty_type_dd    = ft.Dropdown(label="Qty Type",        width=120, value="Pieces", options=[ft.dropdown.Option("Pieces"), ft.dropdown.Option("Boxes")], **S)
        
        # Case tracking
        self.total_order_cases = ft.TextField(label="Tot Ord Cases", width=100, value="0", read_only=True, **S)
        self.packed_cases      = ft.TextField(label="Packed Cases",  width=100, value="0", read_only=True, **S)
        self.balance_cases     = ft.TextField(label="Balance",       width=100, value="0", read_only=True, **S)

        # ── Footer fields ────────────────────────────────────
        self.total_pcs   = ft.Text("Total Pcs: 0",   size=13, weight="bold")
        self.total_boxes = ft.Text("Total Boxes: 0", size=13, weight="bold")
        self.trade_disc  = ft.TextField(label="Trade %",    value="0", width=80, on_change=self._calc, **S)
        self.scheme_disc = ft.TextField(label="Scheme %",   value="0", width=80, on_change=self._calc, **S)
        self.fest_disc   = ft.TextField(label="Festival %", value="0", width=80, on_change=self._calc, **S)
        self.spec_disc   = ft.TextField(label="Special %",  value="0", width=80, on_change=self._calc, **S)
        self.cash_disc   = ft.TextField(label="Cash %",     value="0", width=80, on_change=self._calc, **S)

        # --- Dynamic discount ordering ---
        self.DEFAULT_DISCOUNT_ORDER = ["trade", "scheme", "festival", "scd", "cd"]
        self.DISCOUNT_MAP = {
            "trade":    {"field": self.trade_disc,  "label": "Trade %"},
            "scheme":   {"field": self.scheme_disc, "label": "Scheme %"},
            "festival": {"field": self.fest_disc,   "label": "Festival %"},
            "scd":      {"field": self.spec_disc,   "label": "Special %"},
            "cd":       {"field": self.cash_disc,   "label": "Cash %"},
        }
        self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self.discount_row = ft.Row(spacing=10)
        self._reorder_discount_fields()
        self.taxable_val = ft.Text("Taxable: ₹0.00",  size=14, weight="bold")
        self.gst_lbl     = ft.Text("GST (5%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.net_amt     = ft.Text("Total: ₹0.00",    size=20, weight="bold", color=AppColors.PRIMARY)

        # Print/Export options
        self.print_mode = ft.RadioGroup(content=ft.Row([
            ft.Radio(value="Laser",      label="Laser"),
            ft.Radio(value="Dot Matrix", label="Dot Matrix"),
        ]), value="Laser")
        self.export_word = ft.Checkbox(label="Export To Word", value=False)
        self.aft_dis_amt = ft.Text("AftDis Amt: ₹0.00", size=13, weight="w500")
        self.round_off   = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self._calc, **S)

        # ── Scrollable items ──────────────────────────────────
        self.items_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

        self.controls = [
            self._build_header(),
            self._build_col_header(),
            self.items_col,
            ft.Divider(height=1, color="#E2E8F0"),
            self._build_footer(),
        ]

    # ─────────────────────────────────────────────────────────
    # UI builders
    # ─────────────────────────────────────────────────────────
    def _build_header(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            content=ft.Column([
                # Row 1: Title and Slip Info
                ft.Row([
                    ft.Row([
                        ft.Text("Packing Slip", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15),
                    ft.Row([self.slip_no, self.slip_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Party and Tracking
                ft.Row([
                    self.party_dd, self.agent_dd, self.trans_dd, self.dest,
                ], spacing=12, wrap=True),
                
                # Row 3: Order Details
                ft.Row([
                    self.party_order_no, self.party_order_dt, self.order_by, self.order_thro, self.qty_type_dd,
                ], spacing=12, wrap=True),

                # Row 4: Cases & Prep
                ft.Row([
                    self.total_order_cases, self.packed_cases, self.balance_cases, self.cases,
                    ft.VerticalDivider(width=20),
                    self.prepared, self.checked, self.packed_by,
                ], spacing=12, wrap=True),

                # Row 5: Additional Info
                ft.Row([
                    self.docs_by,
                    ft.VerticalDivider(width=20),
                    self.compliments,
                ], spacing=30, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=15),
        )

    def _build_col_header(self):
        return ft.Container(
            bgcolor="#F1F5F9",
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            content=ft.Row([
                ft.Text("ORDER NO",  width=110, size=11, weight="bold"),
                ft.Text("ITEM NAME", width=185, size=11, weight="bold"),
                ft.Text("SIZES",     width=90,  size=11, weight="bold"),
                ft.Text("RATE",      width=70,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("ORD QTY",  width=70,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("AVAIL",     width=60,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("PACK QTY", width=90,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("AMOUNT",   expand=True, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
            ]),
        )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Column([
                # Totals and Discounts
                ft.Row([
                    ft.Column([
                        ft.Row([self.total_pcs, ft.Text(" | ", color="#999"), self.total_boxes]),
                        self.print_mode,
                        self.export_word,
                    ], spacing=5),
                    ft.Container(expand=True),
                    ft.Column([
                        self.discount_row,
                        ft.Row([self.aft_dis_amt, ft.VerticalDivider(), self.round_off], alignment=ft.MainAxisAlignment.END),
                    ], horizontal_alignment=ft.CrossAxisAlignment.END),
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                # Final Actions
                ft.Row([
                    ft.Column([self.taxable_val, self.gst_lbl], spacing=2),
                    ft.Container(expand=True),
                    self.net_amt,
                    ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.did_mount(), tooltip="Refresh Data"),
                    ft.ElevatedButton(
                        "Confirm & Save Slip", icon=ft.icons.SAVE_ALT,
                        on_click=self.save_slip, height=50,
                        style=AppStyles.primary_button_style(),
                    ),
                ]),
            ], spacing=15),
        )

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────
    def did_mount(self):
        self._load_dropdowns()

    def _load_dropdowns(self):
        if not state.company_id:
            return
        parties      = select("parties",      {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        agents       = select("agents",       {"company_id": state.company_id})
        items        = select("items",        {"company_id": state.company_id})
        self._all_items_meta = {str(i["id"]): i for i in items}
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        
        if not self.slip_no.value:
            self.slip_no.value = f"PS-{uuid.uuid4().hex[:6].upper()}"
            
        if self.page:
            self.update()

    # ─────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────
    def on_party_change(self, e):
        party_id = self.party_dd.value
        if not party_id:
            return
        pdata = select("parties", {"id": party_id})
        if pdata:
            p = pdata[0]
            if p.get("transporter_id"): self.trans_dd.value   = str(p["transporter_id"])
            if p.get("agent_id"):       self.agent_dd.value   = str(p["agent_id"])
            self.dest.value = p.get("delivery_city") or p.get("billing_city", "")
            self.trade_disc.value  = str(p.get("discount_trade",    0))
            self.scheme_disc.value = str(p.get("discount_scheme",   0))
            self.fest_disc.value   = str(p.get("discount_festival", 0))
            self.spec_disc.value   = str(p.get("discount_scd",      0))
            self.cash_disc.value   = str(p.get("discount_cd",       0))
            self._party_gst_rate   = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type   = p.get("tax_type", "GST") or "GST"
            # Load dynamic discount order
            self._load_discount_order(p.get("discount_order"))
        self._load_pending_orders(party_id)

    def _calc(self, e=None):
        self._update_totals()
        if self.page:
            self.update()

    # ─── Dynamic Discount Order Helpers ──────────────────────
    def _reorder_discount_fields(self):
        """Rebuild the discount_row with fields in the current _discount_order."""
        self.discount_row.controls = []
        for key in self._discount_order:
            meta = self.DISCOUNT_MAP.get(key)
            if meta:
                self.discount_row.controls.append(meta["field"])

    def _load_discount_order(self, raw_order):
        """Parse discount_order from party data and reorder the footer fields."""
        if raw_order:
            if isinstance(raw_order, str):
                try:
                    order = json.loads(raw_order)
                except Exception:
                    order = list(self.DEFAULT_DISCOUNT_ORDER)
            elif isinstance(raw_order, list):
                order = list(raw_order)
            else:
                order = list(self.DEFAULT_DISCOUNT_ORDER)
            if set(order) == set(self.DEFAULT_DISCOUNT_ORDER) and len(order) == 5:
                self._discount_order = order
            else:
                self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        else:
            self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self._reorder_discount_fields()

    # ─────────────────────────────────────────────────────────
    # Order loading
    # ─────────────────────────────────────────────────────────
    def _load_pending_orders(self, party_id):
        self._pending_items = []
        self.items_col.controls = [
            ft.Container(
                padding=40,
                content=ft.Row([ft.ProgressRing(), ft.Text("  Loading pending orders…")]),
            )
        ]
        if self.page:
            self.items_col.update()

        try:
            orders = select("orders", {"party_id": party_id, "company_id": state.company_id})
            if not orders:
                self._rebuild_grid()
                return

            pending = [o for o in orders if o.get("status") in ("Pending", "Partial")]
            if not pending:
                self._rebuild_grid()
                return

            # Auto-fill header from the first pending order
            first = pending[0]
            if not self.dest.value:       self.dest.value       = first.get("destination", "")
            if not self.order_by.value:   self.order_by.value   = first.get("order_by", "")
            if not self.order_thro.value: self.order_thro.value = first.get("order_thro", "DIRECT")
            if not self.docs_by.value:    self.docs_by.value    = first.get("documents_by", "Direct")
            
            if self.page: self.update()

            order_ids = [str(o["id"]) for o in pending]
            order_map = {str(o["id"]): o for o in pending}

            # 2. BULK SELECT all items for these orders
            all_o_items = select("order_items", {"order_id": order_ids})
            if not all_o_items:
                self._rebuild_grid()
                return
            
            # 3. BULK SELECT all packed items for these orders to calculate availability
            all_packed = select("packing_slip_items", {"order_id": order_ids, "company_id": state.company_id})
            
            # Group packed items by (order_id, item_id, size_value)
            packed_map = {}
            for r in all_packed:
                k = (str(r["order_id"]), str(r["item_id"]), r["size_value"])
                packed_map[k] = packed_map.get(k, 0) + int(r.get("qty_pieces", 0))

            S = AppStyles.get_input_style()
            for oi in all_o_items:
                order_id   = str(oi["order_id"])
                item_id    = str(oi["item_id"])
                size_val   = oi["size_value"]
                order_qty  = int(oi.get("qty_pieces", 0))
                rate       = float(oi.get("rate", 0))
                order_no   = order_map.get(order_id, {}).get("order_no", "ORD")

                # Calculate already-packed qty from our memory map
                already_packed = packed_map.get((order_id, item_id, size_val), 0)
                available      = order_qty - already_packed
                
                if available <= 0:
                    continue

                meta  = self._all_items_meta.get(item_id, {})
                inner = meta.get("pcs_per_inner_box",  1) or 1
                outer = meta.get("boxes_per_outer_box", 1) or 1
                key   = f"{order_id}__{item_id}__{size_val}"

                tf = ft.TextField(
                    value=str(available), width=80,
                    text_align=ft.TextAlign.CENTER,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda e, k=key, av=available: self._clamp(e, k, av),
                    **S,
                )
                self._pending_items.append({
                    "order_id": order_id, "order_no": order_no,
                    "item_id": item_id, "item_name": meta.get("item_name", ""),
                    "size_value": size_val, "rate": rate,
                    "order_qty": order_qty, "available": available,
                    "inner": inner, "outer": outer,
                    "tf": tf, "key": key,
                })
            self._rebuild_grid()
        except Exception as e:
            print(f"Error loading pending orders: {e}")
            self.items_col.controls = [ft.Text(f"Error loading orders: {e}", color="red")]
            if self.page: self.items_col.update()

    def _clamp(self, e, key, available):
        try:
            v = int(e.control.value or 0)
            if v > available:
                e.control.value    = str(available)
                e.control.error_text = f"Max {available}"
            elif v < 0:
                e.control.value = "0"
            else:
                e.control.error_text = None
        except ValueError:
            e.control.value = "0"
        self._update_totals()
        if self.page:
            self.update()

    # ─────────────────────────────────────────────────────────
    # Grid
    # ─────────────────────────────────────────────────────────
    def _rebuild_grid(self):
        if not self._pending_items:
            self.items_col.controls = [
                ft.Container(
                    padding=40,
                    content=ft.Text("No pending orders for this party.", color=AppColors.TEXT_SUB),
                )
            ]
        else:
            self.items_col.controls = [self._make_row(it) for it in self._pending_items]
        self._update_totals()
        if self.page:
            self.items_col.update()

    def _make_row(self, it):
        try:
            pcs = int(it["tf"].value or 0)
        except Exception:
            pcs = 0
        amount = pcs * it["rate"]
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                ft.Text(it["order_no"],            width=110, size=12, color=AppColors.PRIMARY),
                ft.Text(it["item_name"],           width=185, size=13, weight="w500"),
                ft.Text(it["size_value"],          width=90,  size=11, italic=True, color=AppColors.TEXT_SUB),
                ft.Text(f"₹{it['rate']}",         width=70,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(str(it["order_qty"]),      width=70,  size=12, text_align=ft.TextAlign.RIGHT),
                ft.Text(str(it["available"]),      width=60,  size=12, text_align=ft.TextAlign.RIGHT, color="green"),
                it["tf"],
                ft.Text(f"₹{amount:,.2f}", expand=True, size=13, weight="bold",
                        text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY),
            ]),
        )

    # ─────────────────────────────────────────────────────────
    # Totals
    # ─────────────────────────────────────────────────────────
    def _update_totals(self):
        total_pcs = total_boxes = gross = 0.0
        for it in self._pending_items:
            try:
                pcs = int(it["tf"].value or 0)
            except Exception:
                pcs = 0
            boxes  = pcs / ((it["inner"] or 1) * (it["outer"] or 1))
            amount = pcs * it["rate"]
            total_pcs   += pcs
            total_boxes += boxes
            gross       += amount
        try:
            val = gross
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    d = float(meta["field"].value or 0)
                    val -= val * (d / 100)
            gst = val * (self._party_gst_rate / 100)
            # Update Footer Labels
            self.total_pcs.value   = f"Total Pcs: {int(total_pcs)}"
            self.total_boxes.value = f"Total Boxes: {total_boxes:.1f}"
            self.aft_dis_amt.value = f"AftDis Amt: ₹{val:,.2f}"
            self.taxable_val.value = f"Taxable: ₹{val:,.2f}"
            self.gst_lbl.value     = f"{self._party_tax_type} ({self._party_gst_rate:.0f}%): ₹{gst:,.2f}"
            
            roff = float(self.round_off.value or 0)
            self.net_amt.value     = f"Total: ₹{val + gst + roff:,.2f}"
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────
    def save_slip(self, e):
        if not self.party_dd.value:
            self._snack("Select a party first!", "red")
            return

        rows_to_pack = []
        for it in self._pending_items:
            try:
                qty = int(it["tf"].value or 0)
            except Exception:
                qty = 0
            if qty > 0:
                rows_to_pack.append((it, qty))

        if not rows_to_pack:
            self._snack("Enter pack quantity for at least one item!", "orange")
            return

        try:
            # Build totals
            total_pcs = sum(q for _, q in rows_to_pack)
            total_boxes = sum(q / ((it["inner"] or 1) * (it["outer"] or 1)) for it, q in rows_to_pack)
            gross = sum(q * it["rate"] for it, q in rows_to_pack)
            val = gross
            for f in [self.trade_disc, self.scheme_disc]:
                val -= val * (float(f.value or 0) / 100)
            gst = val * (self._party_gst_rate / 100)

            # Calculate discount amounts for database
            td_amt  = val * (float(self.trade_disc.value or 0) / 100)
            val_td  = val - td_amt
            spd_amt = val_td * (float(self.scheme_disc.value or 0) / 100)
            
            slip_no = str(self.slip_no.value or f"PS-{uuid.uuid4().hex[:6].upper()}")
            slip_dt = str(self.slip_date.value or date.today().isoformat())
            slip_yr = slip_dt.split("-")[0] if "-" in slip_dt else ""

            header = {
                "company_id":     state.company_id,
                "slip_no":        slip_no,
                "slip_year":      slip_yr,
                "slip_date":      slip_dt,
                "party_id":       self.party_dd.value,
                "agent_id":       self.agent_dd.value,
                "transporter_id": self.trans_dd.value,
                "destination":    self.dest.value,
                "documents_by":   self.docs_by.value,
                "party_order_no": self.party_order_no.value,
                "party_order_date": self.party_order_dt.value or None,
                "order_by":       self.order_by.value,
                "order_thro":     self.order_thro.value,
                "qty_type":       self.qty_type_dd.value,
                "compliments":    self.compliments.value,
                "total_order_cases": int(self.total_order_cases.value or 0),
                "packed_cases":      int(self.packed_cases.value or 0),
                "no_of_cases":       int(self.cases.value or 0),
                "prepared_by":    self.prepared.value,
                "checked_by":     self.checked.value,
                "packed_by":      self.packed_by.value,
                "barcode_type":   self.print_mode.value,
                "export_to_word": self.export_word.value,
                "no_of_items":    len(rows_to_pack),
                "total_pcs":      int(total_pcs),
                "total_boxes":    round(total_boxes, 2),
                "total_amount":   round(gross, 2),
                "aftdis_amount":  round(val, 2),
                "td_percent":     float(self.trade_disc.value  or 0),
                "td_amount":      round(td_amt, 2),
                "spd_percent":    float(self.scheme_disc.value or 0),
                "spd_amount":     round(spd_amt, 2),
                "festival_percent": float(self.fest_disc.value or 0),
                "scd_percent":    float(self.spec_disc.value   or 0),
                "cd_percent":     float(self.cash_disc.value   or 0),
                "tax_type":       self._party_tax_type,
                "tax_per":        self._party_gst_rate,
                "tax_amount":     round(gst, 2),
                "round_off":      float(self.round_off.value or 0),
                "net_amount":     round(val + gst + float(self.round_off.value or 0), 2),
                "status":         "Unbilled",
            }
            
            # Fetch company details for PDF
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}

            res = insert("packing_slips", header)
            if not res:
                raise Exception("Failed to create packing slip header")
            slip_id = res[0]["id"]

            # Insert items + update order status
            packed_items_for_pdf = []
            packed_by_order = {}
            for it, qty in rows_to_pack:
                boxes  = qty / ((it["inner"] or 1) * (it["outer"] or 1))
                amount = qty * it["rate"]
                item_row = {
                    "company_id":     state.company_id,
                    "packing_slip_id": slip_id,
                    "order_id":       it.get("order_id") or None,
                    "item_id":        it.get("item_id") or None,
                    "item_name":      it.get("item_name") or "",
                    "size_value":     it.get("size_value") or "",
                    "rate":           it.get("rate") or 0,
                    "qty_pieces":     qty,
                    "qty_boxes":      round(boxes, 2),
                    "amount":         round(amount, 2),
                }
                insert("packing_slip_items", item_row)
                packed_items_for_pdf.append(item_row)
                
                packed_by_order.setdefault(it["order_id"], {"packed": 0, "total": 0})
                packed_by_order[it["order_id"]]["packed"] += qty
                packed_by_order[it["order_id"]]["total"]  += it["order_qty"]

            # Generate PDF
            header["party_name"] = "Customer"
            if self.party_dd.value:
                party_data = select("parties", {"id": self.party_dd.value})
                if party_data: header["party_name"] = party_data[0]["name"]
            
            pdf_path = pdf_engine.generate_packing_slip(header, packed_items_for_pdf, company)
            print_pdf(pdf_path)

            # Update order statuses
            for order_id, counts in packed_by_order.items():
                new_status = "Packed" if counts["packed"] >= counts["total"] else "Partial"
                update("orders", {"status": new_status}, {"id": order_id})

            self._snack(f"✅ Packing Slip {slip_no} saved and PDF generated!", "green")
            self._clear()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────
    def _snack(self, msg, color):
        if self.page:
            self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
            self.page.snack_bar.open = True
            self.page.update()

    def _clear(self):
        self._pending_items = []
        self.items_col.controls = []
        self.slip_no.value = f"PS-{uuid.uuid4().hex[:6].upper()}"
        self.party_dd.value = None
        self.agent_dd.value = None
        self.trans_dd.value = None
        self.dest.value     = ""
        self.cases.value    = "0"
        self.prepared.value = self.checked.value = self.packed_by.value = ""
        self.trade_disc.value = self.scheme_disc.value = "0"
        self.fest_disc.value = self.spec_disc.value = self.cash_disc.value = "0"
        self.round_off.value = "0.00"
        self.total_pcs.value = "Total Pcs: 0"
        self.total_boxes.value = "Total Boxes: 0"
        self.aft_dis_amt.value = "AftDis Amt: ₹0.00"
        self.taxable_val.value = "Taxable: ₹0.00"
        self.gst_lbl.value = "GST (5%): ₹0.00"
        self.net_amt.value = "Total: ₹0.00"
        
        # New header fields
        self.party_order_no.value = ""
        self.party_order_dt.value = date.today().isoformat()
        self.order_by.value       = ""
        self.compliments.value    = ""
        self.total_order_cases.value = "0"
        self.packed_cases.value      = "0"
        self.balance_cases.value     = "0"
        
        self._update_totals()
        if self.page:
            try:
                self.items_col.update()
                self.update()
                self.page.update()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────
    # History & Printing
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        slips = select("packing_slips", {"company_id": state.company_id})
        slips.sort(key=lambda x: x.get("slip_date", ""), reverse=True)
        
        parties = select("parties", {"company_id": state.company_id})
        party_map = {str(p["id"]): p["name"] for p in parties}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for s in slips:
            p_name = party_map.get(str(s.get("party_id")), "Unknown")
            s["party_name"] = p_name
            
            lv.controls.append(
                ft.Container(
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{s.get('slip_no')}  |  {s.get('slip_date')}", weight="bold", size=14),
                            ft.Text(f"Created: {(s.get('created_at') or '').replace('T', ' ')[:16]}", size=10, color=ft.colors.BLUE_GREY_400),
                            ft.Text(p_name, size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"Pcs: {s.get('total_pcs', 0)}", size=12),
                        ft.Text(f"Boxes: {float(s.get('total_boxes', 0)):.1f}", size=12),
                        ft.IconButton(ft.icons.PRINT, tooltip="Print Slip", icon_color=ft.colors.BLUE_700, 
                                      on_click=lambda e, ps=s: self.print_history_slip(ps))
                    ])
                )
            )
            
        dlg = ft.AlertDialog(
            title=ft.Text("Recent Packing Slips"),
            content=ft.Container(width=600, height=400, content=lv),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def print_history_slip(self, slip):
        try:
            items = select("packing_slip_items", {"slip_id": slip["id"]})
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            pdf_path = pdf_engine.generate_packing_slip(slip, items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing: {ex}", "red")
