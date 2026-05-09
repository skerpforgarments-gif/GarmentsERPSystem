import flet as ft
import uuid
import os
import json
import math
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no, get_next_doc_no
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

        self._pending_items        = []   # list of row-data dicts
        self._pending_orders_map   = {}   # map of order_id -> order_data
        self._selected_item_keys  = set() # tracked selected keys
        self._all_items_meta       = {}
        self._packed_slip_data     = []   # cached packing slip headers for this party
        self._packed_items_data    = []   # cached packing slip items for these orders
        self._party_gst_rate       = 5.0
        self._party_tax_type       = "GST"
        self._calculating          = False
        self.current_edit_id       = None

        # ── Header ───────────────────────────────────────────
        S = AppStyles.get_input_style()
        self.slip_no   = ft.TextField(label="Slip No",   width=130, **S)
        self.slip_date = ft.TextField(label="Date",      width=130, value=date.today().isoformat(), **S)
        self.party_dd  = ft.Dropdown(label="Select Party *", width=280, on_change=self.on_party_change, **S)
        self.agent_dd  = ft.Dropdown(label="Agent",      width=180, **S)
        self.trans_dd  = ft.Dropdown(label="Transporter",width=200, **S)
        self.dest      = ft.TextField(label="Destination",width=160, **S)
        self.cases     = ft.TextField(label="No of Cases",width=100, value="0", keyboard_type=ft.KeyboardType.NUMBER, on_change=self._update_case_balance, **S)
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
        self.group_items       = ft.Switch(label="Group by Item", value=False, on_change=lambda _: self._load_pending_orders(self.party_dd.value), active_color=AppColors.PRIMARY)

        self.total_pcs   = ft.Text("Total Pcs: 0",   size=13, weight="bold")
        self.total_boxes = ft.Text("Total Boxes: 0", size=13, weight="bold")

        self.taxable_val = ft.Text("Taxable: ₹0.00",  size=14, weight="bold")
        self.gst_lbl     = ft.Text("GST (5%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.net_amt     = ft.Text("Total: ₹0.00",    size=20, weight="bold", color=AppColors.PRIMARY)

        self.print_mode = ft.RadioGroup(content=ft.Row([
            ft.Radio(value="Laser",      label="Laser"),
            ft.Radio(value="Dot Matrix", label="Dot Matrix"),
        ]), value="Laser")
        self.export_word = ft.Checkbox(label="Export To Word", value=False)
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
                    ft.Row([self.slip_no, self.slip_date, self.group_items], spacing=10),
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
                ft.Checkbox(on_change=self.toggle_all, tooltip="Select All"),
                ft.Text("ORDER NO",  width=110, size=11, weight="bold"),
                ft.Text("ITEM NAME", width=185, size=11, weight="bold"),
                ft.Text("SIZES",     width=90,  size=11, weight="bold"),
                ft.Text("RATE",      width=70,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("ORD QTY",  width=70,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("BALANCE SHIPMENT", width=120, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
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
                        ft.Row([self.round_off], alignment=ft.MainAxisAlignment.END),
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
        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Customer", "Both"]})
        transporters = select("transporters", {"company_id": state.company_id})
        agents       = select("agents",       {"company_id": state.company_id})
        items        = select("items",        {"company_id": state.company_id, "item_type": ["Sales", "Both"]})
        self._all_items_meta = {str(i["id"]): i for i in items}
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        
        if not self.slip_no.value:
            self.slip_no.value = get_next_doc_no("packing_slips", "P", state.company_id, "slip_no")
            
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
            self._party_gst_rate   = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type   = p.get("tax_type", "GST") or "GST"
        self._load_pending_orders(party_id)

    def _calc(self, e=None):
        self._update_totals()
        if self.page:
            try:
                self.update()
            except Exception:
                pass

    def _update_case_balance(self, e=None):
        """Calculate the remaining balance of cases dynamically."""
        try:
            tot = int(self.total_order_cases.value or 0)
            pck = int(self.packed_cases.value or 0)
            cur = int(self.cases.value or 0)
            self.balance_cases.value = str(tot - pck - cur)
            if self.page:
                self.balance_cases.update()
        except Exception:
            pass

    def toggle_all(self, e):
        """Select or deselect all pending items."""
        if e.control.value:
            self._selected_item_keys = {it["key"] for it in self._pending_items}
        else:
            self._selected_item_keys.clear()
        self._rebuild_grid()

    def on_item_toggle(self, key, val):
        """Track individual item selection."""
        if val:
            self._selected_item_keys.add(key)
        else:
            self._selected_item_keys.discard(key)
        # Rebuild grid so checkbox visuals match the new state
        self._rebuild_grid()



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
            self._pending_orders_map = {str(o["id"]): o for o in pending}

            # 2. BULK SELECT all items for these orders
            all_o_items = select("order_items", {"order_id": order_ids})
            if not all_o_items:
                self._rebuild_grid()
                return
            
            # 3. BULK SELECT all packed items for these orders to calculate availability
            all_packed = select("packing_slip_items", {"order_id": order_ids, "company_id": state.company_id})
            
            # Cache packed data for case tracking in _update_totals
            self._packed_items_data = all_packed
            self._packed_slip_data  = select("packing_slips", {"party_id": party_id, "company_id": state.company_id})
            
            # Group packed items by (order_id, item_id, size_value)
            packed_map = {}
            for r in all_packed:
                k = (str(r["order_id"]), str(r["item_id"]), r["size_value"])
                packed_map[k] = packed_map.get(k, 0) + int(r.get("qty_pieces", 0))

            S = AppStyles.get_input_style()
            
            if self.group_items.value:
                # Grouped Flow: Aggregate by (item_id, size_val)
                grouped_data = {}
                for oi in all_o_items:
                    item_id = str(oi["item_id"])
                    size_val = oi["size_value"]
                    order_id = str(oi["order_id"])
                    order_qty = int(oi.get("qty_pieces", 0))
                    rate = float(oi.get("rate", 0))
                    
                    already_packed = packed_map.get((order_id, item_id, size_val), 0)
                    available = order_qty - already_packed
                    
                    if available <= 0: continue
                    
                    k = (item_id, size_val)
                    if k not in grouped_data:
                        grouped_data[k] = {
                            "item_id": item_id, "size_value": size_val,
                            "rate": rate, "total_available": 0,
                            "sources": [] # [(order_id, avail), ...]
                        }
                    grouped_data[k]["total_available"] += available
                    grouped_data[k]["sources"].append({"order_id": order_id, "avail": available, "order_qty": order_qty})

                for k, g in grouped_data.items():
                    item_id, size_val = k
                    meta = self._all_items_meta.get(item_id, {})
                    inner = meta.get("pcs_per_inner_box", 1) or 1
                    outer = meta.get("boxes_per_outer_box", 1) or 1
                    available = g["total_available"]
                    
                    key = f"GRP__{item_id}__{size_val}"
                    amt_lbl = ft.Text("₹0.00", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY)
                    tf = ft.TextField(
                        value="0", width=80, text_align=ft.TextAlign.CENTER,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        on_change=lambda e, k=key, av=available: self._clamp(e, k, av),
                        **S,
                    )
                    self._pending_items.append({
                        "order_id": "Multiple", "order_no": "GRP",
                        "item_id": item_id, "item_name": meta.get("item_name", "Unknown"),
                        "size_value": size_val, "rate": g["rate"],
                        "order_qty": available, "available": available,
                        "inner": inner, "outer": outer,
                        "tf": tf, "amt_lbl": amt_lbl, "key": key,
                        "sources": g["sources"]
                    })
                    self._selected_item_keys.add(key)
            else:
                for oi in all_o_items:
                    order_id   = str(oi["order_id"])
                    item_id    = str(oi["item_id"])
                    size_val   = oi["size_value"]
                    order_qty  = int(oi.get("qty_pieces", 0))
                    rate       = float(oi.get("rate", 0))
                    order_no   = self._pending_orders_map.get(order_id, {}).get("order_no", "ORD")

                    already_packed = packed_map.get((order_id, item_id, size_val), 0)
                    available      = order_qty - already_packed
                    
                    if available <= 0:
                        continue

                    meta  = self._all_items_meta.get(item_id, {})
                    inner = meta.get("pcs_per_inner_box",  1) or 1
                    outer = meta.get("boxes_per_outer_box", 1) or 1
                    key   = f"{order_id}__{item_id}__{size_val}"

                    amt_lbl = ft.Text("₹0.00", expand=True, size=13, weight="bold",
                                      text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY)
                    tf = ft.TextField(
                        value="0", width=80,
                        text_align=ft.TextAlign.CENTER,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        on_change=lambda e, k=key, av=available: self._clamp(e, k, av),
                        **S,
                    )
                    self._pending_items.append({
                        "order_id": order_id, "order_no": order_no,
                        "item_id": item_id, "item_name": meta.get("item_name", "Unknown"),
                        "size_value": size_val, "rate": rate,
                        "order_qty": order_qty, "available": available,
                        "inner": inner, "outer": outer,
                        "tf": tf, "amt_lbl": amt_lbl, "key": key,
                    })
                    self._selected_item_keys.add(key)
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
            try:
                self.update()
            except Exception:
                pass

    def _make_row(self, it):
        # Update the stored amount label with current value
        try:
            pcs = int(it["tf"].value or 0)
        except Exception:
            pcs = 0
        amount = pcs * it["rate"]
        it["amt_lbl"].value = f"₹{amount:,.2f}"
        
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                ft.Checkbox(
                    value=(it["key"] in self._selected_item_keys),
                    on_change=lambda e, k=it["key"]: self.on_item_toggle(k, e.control.value)
                ),
                ft.Text(it["order_no"],            width=110, size=12, color=AppColors.PRIMARY),
                ft.Text(it["item_name"],           width=185, size=13, weight="w500"),
                ft.Text(it["size_value"],          width=90,  size=11, italic=True, color=AppColors.TEXT_SUB),
                ft.Text(f"₹{it['rate']}",         width=70,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(str(it["order_qty"]),      width=70,  size=12, text_align=ft.TextAlign.RIGHT),
                ft.Text(str(it["available"]),      width=120, size=12, text_align=ft.TextAlign.RIGHT, color="green"),
                it["tf"],
                it["amt_lbl"],
            ]),
        )

    # ─────────────────────────────────────────────────────────
    # Totals
    # ─────────────────────────────────────────────────────────
    def _update_totals(self):
        # Guard against recursive calls
        if self._calculating:
            return
        self._calculating = True

        total_pcs = total_boxes = gross = 0.0
        selected_order_ids = set()

        for it in self._pending_items:
            # Update row-level amount label regardless of selection
            try:
                row_pcs = int(it["tf"].value or 0)
            except Exception:
                row_pcs = 0
            row_amt = row_pcs * it["rate"]
            if "amt_lbl" in it:
                it["amt_lbl"].value = f"₹{row_amt:,.2f}"

            # Skip unselected items for footer totals
            if it["key"] not in self._selected_item_keys:
                continue
            
            selected_order_ids.add(str(it["order_id"]))
            inner = it["inner"] or 1
            outer = it.get("outer", 1) or 1
            boxes = row_pcs / (inner * outer)
            total_pcs   += row_pcs
            total_boxes += boxes
            gross       += row_amt
        
        # Case Tracking from cached data (no DB calls)
        tot_ord_cases = 0
        packed_cases  = 0
        for oid in selected_order_ids:
            ord_data = self._pending_orders_map.get(oid, {})
            tot_ord_cases += int(ord_data.get("no_of_cases") or 0)
        
        if selected_order_ids:
            slip_ids = {str(r["packing_slip_id"]) for r in self._packed_items_data
                        if r.get("packing_slip_id") and str(r.get("order_id")) in selected_order_ids}
            if slip_ids:
                packed_cases = sum(int(s.get("no_of_cases") or 0)
                                  for s in self._packed_slip_data
                                  if str(s["id"]) in slip_ids)

        self.total_order_cases.value = str(tot_ord_cases)
        self.packed_cases.value      = str(packed_cases)
        self._update_case_balance()

        # Footer totals
        gst  = gross * (self._party_gst_rate / 100)
        
        subtotal = gross + gst
        final_amt = math.ceil(subtotal)
        roff = final_amt - subtotal

        self.total_pcs.value   = f"Total Pcs: {int(total_pcs)}"
        self.total_boxes.value = f"Total Boxes: {math.ceil(total_boxes)}"
        self.taxable_val.value = f"Taxable: ₹{gross:,.2f}"
        self.gst_lbl.value     = f"{self._party_tax_type} ({self._party_gst_rate:.0f}%): ₹{gst:,.2f}"
        self.round_off.value   = f"{roff:.2f}"
        self.net_amt.value     = f"Total: ₹{final_amt:,.2f}"

        self._calculating = False

    # ─────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────
    def save_slip(self, e):
        if not self.party_dd.value:
            self._snack("Select a party first!", "red")
            return

        rows_to_pack = []
        for it in self._pending_items:
            # Skip unselected items
            if it["key"] not in self._selected_item_keys:
                continue

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
            total_boxes = sum(q / ((it["inner"] or 1) * (it.get("outer", 1) or 1)) for it, q in rows_to_pack)
            total_boxes = math.ceil(total_boxes)
            gross = sum(q * it["rate"] for it, q in rows_to_pack)
            gst = gross * (self._party_gst_rate / 100)
            td_amt = 0
            spd_amt = 0
            val = gross
            
            slip_no = str(self.slip_no.value or get_next_doc_no("packing_slips", "P", state.company_id, "slip_no"))
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
                "aftdis_amount":  round(gross, 2),
                "td_percent":     0,
                "td_amount":      0,
                "spd_percent":    0,
                "spd_amount":     0,
                "festival_percent": 0,
                "scd_percent":    0,
                "cd_percent":     0,
                "tax_type":       self._party_tax_type,
                "tax_per":        self._party_gst_rate,
                "tax_amount":     round(gst, 2),
                "round_off":      float(self.round_off.value or 0),
                "net_amount":     round(gross + gst + float(self.round_off.value or 0), 2),
                "status":         "Unbilled",
            }
            
            # Fetch company details for PDF
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}

            if self.current_edit_id:
                # Update existing slip
                slip_id = self.current_edit_id
                update("packing_slips", header, {"id": slip_id})
                # Clear old items
                delete("packing_slip_items", {"packing_slip_id": slip_id})
            else:
                res = insert("packing_slips", header)
                if not res:
                    raise Exception("Failed to create packing slip header")
                slip_id = res[0]["id"]

            # Insert items + update order status
            packed_items_for_pdf = []
            packed_by_order = {}
            
            for it, qty in rows_to_pack:
                # Distribute quantity across source orders (if grouped)
                fulfillments = []
                if it["key"].startswith("GRP__"):
                    remaining = qty
                    for src in it.get("sources", []):
                        if remaining <= 0: break
                        take = min(remaining, src["avail"])
                        fulfillments.append({
                            "order_id": src["order_id"],
                            "qty": take,
                            "order_qty": src["order_qty"]
                        })
                        remaining -= take
                else:
                    fulfillments.append({
                        "order_id": it["order_id"],
                        "qty": qty,
                        "order_qty": it["order_qty"]
                    })

                for f in fulfillments:
                    f_qty = f["qty"]
                    boxes  = f_qty / ((it["inner"] or 1) * (it["outer"] or 1))
                    amount = f_qty * it["rate"]
                    
                    item_row = {
                        "company_id":     state.company_id,
                        "packing_slip_id": slip_id,
                        "order_id":       f["order_id"],
                        "item_id":        it.get("item_id"),
                        "item_name":      it.get("item_name") or "",
                        "size_value":     it.get("size_value") or "",
                        "rate":           it.get("rate") or 0,
                        "qty_pieces":     f_qty,
                        "qty_boxes":      math.ceil(boxes),
                        "amount":         round(amount, 2),
                    }
                    insert("packing_slip_items", item_row)
                    packed_items_for_pdf.append(item_row)
                    
                    oid = f["order_id"]
                    packed_by_order.setdefault(oid, {"packed": 0, "total": 0})
                    packed_by_order[oid]["packed"] += f_qty
                    packed_by_order[oid]["total"]  = f["order_qty"] # Note: we use the order item's total qty

            # Collect unique internal order numbers for the PDF header
            unique_orders = set()
            for it, qty in rows_to_pack:
                oid = str(it.get("order_id"))
                if oid in self._pending_orders_map:
                    unique_orders.add(self._pending_orders_map[oid].get("order_no", "ORD"))
            header["order_no"] = ", ".join(sorted(list(unique_orders)))

            pdf_path = pdf_engine.generate_packing_slip(header, packed_items_for_pdf, company)
            print_pdf(pdf_path)

            # Update order statuses
            for order_id in packed_by_order.keys():
                # 1. Total pieces required in this order
                o_items = select("order_items", {"order_id": order_id})
                total_req = sum(int(oi.get("qty_pieces", 0)) for oi in o_items)
                
                # 2. Total pieces already packed (including those in THIS current slip)
                p_items = select("packing_slip_items", {"order_id": order_id})
                total_packed = sum(int(pi.get("qty_pieces", 0)) for pi in p_items)
                
                new_status = "Packed" if total_packed >= total_req else "Partial"
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
        self.slip_no.value = get_next_doc_no("packing_slips", "P", state.company_id, "slip_no")
        self.party_dd.value = None
        self.agent_dd.value = None
        self.trans_dd.value = None
        self.dest.value     = ""
        self.cases.value    = "0"
        self.prepared.value = self.checked.value = self.packed_by.value = ""
        self.round_off.value = "0.00"
        self.total_pcs.value = "Total Pcs: 0"
        self.total_boxes.value = "Total Boxes: 0"
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
        
        self._selected_item_keys.clear()
        self.current_edit_id = None
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
                        ft.Row([
                            ft.IconButton(ft.icons.EDIT_OUTLINED, tooltip="Edit Slip", icon_color=AppColors.PRIMARY,
                                          on_click=lambda e, ps=s: self.load_slip_for_edit(ps, dlg)),
                            ft.IconButton(ft.icons.PRINT, tooltip="Print Slip", icon_color=ft.colors.BLUE_700, 
                                          on_click=lambda e, ps=s: self.print_history_slip(ps)),
                            ft.IconButton(ft.icons.DELETE_OUTLINE, tooltip="Delete Slip", icon_color="red",
                                          on_click=lambda e, ps=s: self.delete_slip_from_history(ps, dlg))
                        ])
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

    def delete_slip_from_history(self, slip, dlg):
        """Deletes a packing slip and its items, ensuring it's not billed."""
        def confirm_delete(e):
            try:
                # Check if billed in a transport invoice
                linked = select("transport_invoice_items", {"packing_slip_id": slip["id"]})
                if linked:
                    confirm_dlg.open = False
                    self.page.update()
                    self._snack("Cannot delete: This slip is already included in a Transport Invoice.", "orange")
                    return

                # Identify affected orders before deletion
                items = select("packing_slip_items", {"packing_slip_id": slip["id"]})
                order_ids = list({str(it["order_id"]) for it in items if it.get("order_id")})

                # 1. Delete items
                delete("packing_slip_items", {"packing_slip_id": slip["id"]})
                # 2. Delete header
                delete("packing_slips", {"id": slip["id"]})
                
                # 3. Recalculate status for each affected order
                for oid in order_ids:
                    # Total pieces required
                    o_items = select("order_items", {"order_id": oid})
                    total_req = sum(int(oi.get("qty_pieces", 0)) for oi in o_items)
                    
                    # Total pieces still packed (after deletion)
                    p_items = select("packing_slip_items", {"order_id": oid})
                    total_packed = sum(int(pi.get("qty_pieces", 0)) for pi in p_items)
                    
                    if total_packed == 0:
                        new_status = "Pending"
                    elif total_packed >= total_req:
                        new_status = "Packed"
                    else:
                        new_status = "Partial"
                    
                    update("orders", {"status": new_status}, {"id": oid})
                
                confirm_dlg.open = False
                dlg.open = False
                self.page.update()
                self._snack(f"Slip {slip.get('slip_no')} deleted.", "green")
                self.show_history_modal(None)
            except Exception as ex:
                self._snack(f"Delete Error: {ex}", "red")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete slip {slip.get('slip_no')}?"),
            actions=[
                ft.TextButton("Yes, Delete", on_click=confirm_delete, style=ft.ButtonStyle(color="red")),
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(confirm_dlg))
            ]
        )
        self.page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def load_slip_for_edit(self, slip, dlg):
        """Loads a past packing slip into the main form for editing."""
        try:
            self._close_dialog(dlg)
            self._clear()
            
            self.current_edit_id    = slip["id"]
            self.slip_no.value      = slip.get("slip_no", "")
            self.slip_date.value    = slip.get("slip_date", "")
            self.party_dd.value     = str(slip.get("party_id")) if slip.get("party_id") else None
            self.agent_dd.value     = str(slip.get("agent_id")) if slip.get("agent_id") else None
            self.trans_dd.value     = str(slip.get("transporter_id")) if slip.get("transporter_id") else None
            self.dest.value         = slip.get("destination", "")
            self.docs_by.value      = slip.get("documents_by", "Direct")
            self.party_order_no.value = slip.get("party_order_no", "")
            self.party_order_dt.value = slip.get("party_order_date", "")
            self.order_by.value     = slip.get("order_by", "")
            self.order_thro.value   = slip.get("order_thro", "DIRECT")
            self.qty_type_dd.value  = slip.get("qty_type", "Pieces")
            self.compliments.value  = slip.get("compliments", "")
            self.cases.value        = str(slip.get("no_of_cases", 0))
            self.prepared.value     = slip.get("prepared_by", "")
            self.checked.value      = slip.get("checked_by", "")
            self.packed_by.value    = slip.get("packed_by", "")
            self.round_off.value    = str(slip.get("round_off", "0.00"))

            # Load party GST info
            if self.party_dd.value:
                pdata = select("parties", {"id": self.party_dd.value})
                if pdata:
                    p = pdata[0]
                    self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
                    self._party_tax_type = p.get("tax_type", "GST") or "GST"

            # Load saved items back into the grid
            db_items = select("packing_slip_items", {"packing_slip_id": slip["id"]})
            S = AppStyles.get_input_style()
            self._pending_items = []
            self._selected_item_keys.clear()

            # Build a map of how much was packed by ALL slips (across all orders involved)
            # and how much was packed by THIS slip, so we can compute the real available qty.
            order_ids_involved = list({str(it.get("order_id")) for it in db_items if it.get("order_id")})
            
            # Fetch original order items to get the full order qty
            all_order_items = []
            order_no_map = {}
            for oid in order_ids_involved:
                oi_list = select("order_items", {"order_id": oid})
                all_order_items.extend(oi_list)
                ord_data = select("orders", {"id": oid})
                if ord_data:
                    order_no_map[oid] = ord_data[0].get("order_no", "")

            # Map: (order_id, item_id, size_value) -> original order qty
            order_qty_map = {}
            for oi in all_order_items:
                k = (str(oi["order_id"]), str(oi["item_id"]), oi["size_value"])
                order_qty_map[k] = int(oi.get("qty_pieces", 0))

            # Fetch ALL packed items for these orders (from every packing slip)
            all_packed = select("packing_slip_items", {"order_id": order_ids_involved, "company_id": state.company_id}) if order_ids_involved else []
            
            # Total packed by ALL slips
            total_packed_map = {}
            for r in all_packed:
                k = (str(r["order_id"]), str(r["item_id"]), r["size_value"])
                total_packed_map[k] = total_packed_map.get(k, 0) + int(r.get("qty_pieces", 0))

            # Packed by THIS slip only
            this_slip_map = {}
            for it in db_items:
                k = (str(it.get("order_id", "")), str(it["item_id"]), it.get("size_value", ""))
                this_slip_map[k] = this_slip_map.get(k, 0) + int(it.get("qty_pieces", 0))

            for it in db_items:
                item_id   = str(it["item_id"])
                meta      = self._all_items_meta.get(item_id, {})
                inner     = meta.get("pcs_per_inner_box", 1) or 1
                outer     = meta.get("boxes_per_outer_box", 1) or 1
                size_val  = it.get("size_value", "")
                rate      = float(it.get("rate", 0))
                qty       = int(it.get("qty_pieces", 0))
                order_id  = str(it.get("order_id", ""))
                order_no  = order_no_map.get(order_id, "")

                # Calculate real available: order_qty - packed_by_others
                # packed_by_others = total_packed - this_slip_packed
                lookup_key    = (order_id, item_id, size_val)
                orig_order_qty = order_qty_map.get(lookup_key, qty)
                total_packed   = total_packed_map.get(lookup_key, 0)
                this_slip_qty  = this_slip_map.get(lookup_key, 0)
                packed_by_others = total_packed - this_slip_qty
                available = max(orig_order_qty - packed_by_others, qty)  # at least the current qty

                key = f"{order_id}__{item_id}__{size_val}"
                amt_lbl = ft.Text(f"₹{qty * rate:,.2f}", expand=True, size=13, weight="bold",
                                  text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY)
                tf = ft.TextField(
                    value=str(qty), width=80,
                    text_align=ft.TextAlign.CENTER,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda e, k=key, av=available: self._clamp(e, k, av),
                    **S,
                )
                self._pending_items.append({
                    "order_id": order_id, "order_no": order_no,
                    "item_id": item_id, "item_name": it.get("item_name") or meta.get("item_name", ""),
                    "size_value": size_val, "rate": rate,
                    "order_qty": orig_order_qty, "available": available,
                    "inner": inner, "outer": outer,
                    "tf": tf, "amt_lbl": amt_lbl, "key": key,
                })
                self._selected_item_keys.add(key)

            self._rebuild_grid()
            self._snack(f"Loaded Slip: {self.slip_no.value}", AppColors.PRIMARY)
        except Exception as ex:
            print(f"Edit Load Error: {ex}")
            self._snack(f"Failed to load slip: {ex}", "red")

    def print_history_slip(self, slip):
        try:
            items = select("packing_slip_items", {"slip_id": slip["id"]})
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            pdf_path = pdf_engine.generate_packing_slip(slip, items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing: {ex}", "red")
