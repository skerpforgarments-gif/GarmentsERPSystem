import flet as ft
import uuid
import os
import json
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update
from core.pdf_gen import pdf_engine, print_pdf

class TransportInvoiceTab(ft.Column):
    """
    Transport Invoice (Tirupur 'Original Invoice')
    - Pulls 'Unbilled' Packing Slips for a party
    - Calculates 5-tier sequential discounts
    - Captures LR (Lorry Receipt) details
    """

    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        self._available_slips = []
        self._selected_slips  = set()
        self._party_gst_rate  = 5.0
        self._party_tax_type  = "IGST"

        # ── Header ───────────────────────────────────────────
        S = AppStyles.get_input_style()
        self.inv_no    = ft.TextField(label="Invoice No", width=140, **S)
        self.inv_date  = ft.TextField(label="Date",       width=140, value=date.today().isoformat(), **S)
        self.party_dd  = ft.Dropdown(label="Select Party *", width=280, on_change=self.on_party_change, **S)
        
        # New Header Fields (Align with screenshots)
        self.agent_dd   = ft.Dropdown(label="Agent",       width=160, **S)
        self.trans_dd   = ft.Dropdown(label="Transporter", width=180, **S)
        self.dest       = ft.TextField(label="Destination",width=150, **S)
        self.order_by   = ft.TextField(label="Order By",    width=130, **S)
        self.order_thro = ft.TextField(label="Order Thro'", width=130, **S)
        self.price_list = ft.TextField(label="Price List",  width=150, **S)
        self.qty_type   = ft.TextField(label="Qty Type",    width=100, **S)
        
        # ── LR Details ──────────
        self.lr_no      = ft.TextField(label="LR No",     width=120, **S)
        self.lr_date    = ft.TextField(label="LR Date",   width=120, value=date.today().isoformat(), **S)
        self.no_cases   = ft.TextField(label="No of Cases", width=100, value="0", **S)
        self.case_no    = ft.TextField(label="Case No",    width=120, **S)
        self.weight     = ft.TextField(label="Tot Weight", width=100, value="0", **S)
        self.charges    = ft.TextField(label="Freight",    width=100, value="0", on_change=self._calc, **S)

        # ── Footer Totals ────────────────────────────────────
        self.total_pcs   = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        self.total_boxes = ft.Text("Total Boxes: 0",  size=13, weight="bold")
        
        # Sequential Discounts
        self.td_p   = ft.TextField(label="Trade %",    value="0", width=80, on_change=self._calc, **S)
        self.spd_p  = ft.TextField(label="Scheme %",   value="0", width=80, on_change=self._calc, **S)
        self.fest_p = ft.TextField(label="Festival %", value="0", width=80, on_change=self._calc, **S)
        self.scd_p  = ft.TextField(label="Special %",  value="0", width=80, on_change=self._calc, **S)
        self.cd_p   = ft.TextField(label="Cash %",     value="0", width=80, on_change=self._calc, **S)

        # --- Dynamic discount ordering ---
        self.DEFAULT_DISCOUNT_ORDER = ["trade", "scheme", "festival", "scd", "cd"]
        self.DISCOUNT_MAP = {
            "trade":    {"field": self.td_p,   "label": "Trade %"},
            "scheme":   {"field": self.spd_p,  "label": "Scheme %"},
            "festival": {"field": self.fest_p,  "label": "Festival %"},
            "scd":      {"field": self.scd_p,   "label": "Special %"},
            "cd":       {"field": self.cd_p,    "label": "Cash %"},
        }
        self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self.discount_row = ft.Row(spacing=8)
        self._reorder_discount_fields()

        self.taxable_val = ft.Text("Taxable: ₹0.00", size=14, weight="bold")
        self.gst_lbl     = ft.Text("IGST (5%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.round_off   = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self._calc, **S)
        self.net_amt     = ft.Text("Total: ₹0.00",   size=22, weight="bold", color=AppColors.PRIMARY)

        # ── Items Area ───────────────────────────────────────
        self.items_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

        self.controls = [
            self._build_header(),
            self._build_col_header(),
            self.items_col,
            ft.Divider(height=1, color="#E2E8F0"),
            self._build_footer(),
        ]

    def _build_header(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            content=ft.Column([
                # Row 1: Title and Inv Info
                ft.Row([
                    ft.Row([
                        ft.Text("Transport Invoice", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15),
                    ft.Row([self.inv_no, self.inv_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Party and Tracking
                ft.Row([
                    self.party_dd, self.agent_dd, self.trans_dd, self.dest,
                ], spacing=12, wrap=True),
                
                # Row 3: Order details
                ft.Row([
                    self.order_by, self.order_thro, self.price_list, self.qty_type,
                ], spacing=12, wrap=True),

                # Row 4: LR Details
                ft.Row([
                    self.lr_no, self.lr_date, self.no_cases, self.case_no, self.weight, self.charges
                ], spacing=12, wrap=True),
            ], spacing=15),
        )

    def _build_col_header(self):
        return ft.Container(
            bgcolor="#F1F5F9",
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            content=ft.Row([
                ft.Checkbox(on_change=self.toggle_all),
                ft.Text("SLIP NO",   width=120, size=11, weight="bold"),
                ft.Text("DATE",      width=100, size=11, weight="bold"),
                ft.Text("ITEMS",     width=80,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("PCS",       width=80,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("BOXES",     width=80,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("AMOUNT",    expand=True, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
            ]),
        )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Column([
                ft.Row([
                    ft.Column([self.total_pcs, self.total_boxes], spacing=4),
                    ft.Container(expand=True),
                    ft.Column([
                        self.discount_row,
                        ft.Text("Calculated Sequentially in the order shown above", size=10, italic=True, color="#999")
                    ], horizontal_alignment=ft.CrossAxisAlignment.END)
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                ft.Row([
                    ft.Column([self.taxable_val, self.gst_lbl], spacing=2),
                    ft.Container(expand=True),
                    self.net_amt,
                    ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.did_mount(), tooltip="Refresh Data"),
                    ft.ElevatedButton(
                        "Generate Invoice", icon=ft.icons.RECEIPT_LONG,
                        on_click=self.save_invoice, height=50,
                        style=AppStyles.primary_button_style(),
                    ),
                ]),
            ], spacing=10),
        )

    def did_mount(self):
        self.load_dropdowns()

    def load_dropdowns(self):
        if not state.company_id: return
        parties      = select("parties",      {"company_id": state.company_id})
        agents       = select("agents",       {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        
        if self.page: self.update()

    def on_party_change(self, e):
        party_id = self.party_dd.value
        if not party_id: return
        pdata = select("parties", {"id": party_id})
        if pdata:
            p = pdata[0]
            self.td_p.value   = str(p.get("discount_trade", 0))
            self.spd_p.value  = str(p.get("discount_scheme", 0))
            self.fest_p.value = str(p.get("discount_festival", 0))
            self.scd_p.value  = str(p.get("discount_scd", 0))
            self.cd_p.value   = str(p.get("discount_cd", 0))
            self.dest.value   = p.get("delivery_city") or p.get("billing_city", "")
            self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type = p.get("tax_type", "IGST") or "IGST"
            # Load dynamic discount order
            self._load_discount_order(p.get("discount_order"))
        
        self.load_slips(party_id)

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

    def load_slips(self, party_id):
        self._available_slips = select("packing_slips", {
            "party_id": party_id, 
            "company_id": state.company_id,
            "status": "Unbilled"
        })
        self._selected_slips.clear()
        self.rebuild_grid()

    def toggle_all(self, e):
        if e.control.value:
            self._selected_slips = {str(s["id"]) for s in self._available_slips}
        else:
            self._selected_slips.clear()
        self.rebuild_grid()

    def on_slip_toggle(self, slip_id, val):
        if val: self._selected_slips.add(slip_id)
        else: self._selected_slips.discard(slip_id)
        self._calc()

    def rebuild_grid(self):
        self.items_col.controls = []
        if not self._available_slips:
            self.items_col.controls = [ft.Container(padding=40, content=ft.Text("No unbilled slips found.", color="#999"))]
        else:
            for s in self._available_slips:
                sid = str(s["id"])
                self.items_col.controls.append(
                    ft.Container(
                        bgcolor=ft.colors.WHITE,
                        padding=ft.padding.symmetric(horizontal=24, vertical=12),
                        border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
                        content=ft.Row([
                            ft.Checkbox(value=(sid in self._selected_slips), on_change=lambda e, sid=sid: self.on_slip_toggle(sid, e.control.value)),
                            ft.Text(s["slip_no"], width=120, size=13, weight="bold"),
                            ft.Text(s["slip_date"], width=100, size=13),
                            ft.Text(str(s.get("no_of_items", 0)), width=80, size=13, text_align=ft.TextAlign.RIGHT),
                            ft.Text(str(s.get("total_pcs", 0)),   width=80, size=13, text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"{s.get('total_boxes', 0):.1f}", width=80, size=13, text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"₹{s.get('total_amount', 0):,.2f}", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY),
                        ])
                    )
                )
        self._calc()
        if self.page: self.update()

    def _calc(self, e=None):
        total_pcs = total_boxes = gross = 0.0
        selected_data = [s for s in self._available_slips if str(s["id"]) in self._selected_slips]
        
        for s in selected_data:
            total_pcs   += float(s.get("total_pcs", 0))
            total_boxes += float(s.get("total_boxes", 0))
            gross       += float(s.get("total_amount", 0))

        try:
            # Add Freight
            freight = float(self.charges.value or 0)
            taxable = gross + freight
            
            gst = taxable * (self._party_gst_rate / 100)
            
            self.total_pcs.value   = f"Total Pcs: {int(total_pcs)}"
            self.total_boxes.value = f"Total Boxes: {total_boxes:.1f}"
            self.taxable_val.value = f"Taxable: ₹{taxable:,.2f}"
            self.gst_lbl.value     = f"{self._party_tax_type} ({self._party_gst_rate:.0f}%): ₹{gst:,.2f}"
            self.net_amt.value     = f"Total: ₹{taxable + gst:,.2f}"
        except Exception: pass
        if self.page: self.update()

    def save_invoice(self, e):
        if not self.party_dd.value or not self._selected_slips:
            self._snack("Select party and at least one slip!", "red")
            return
        
        try:
            inv_no = self.inv_no.value or f"TI-{uuid.uuid4().hex[:6].upper()}"
            selected_data = [s for s in self._available_slips if str(s["id"]) in self._selected_slips]
            
            total_pcs = sum(float(s.get("total_pcs", 0)) for s in selected_data)
            total_boxes = sum(float(s.get("total_boxes", 0)) for s in selected_data)
            gross = sum(float(s.get("total_amount", 0)) for s in selected_data)
            
            freight = float(self.charges.value or 0)
            taxable = gross + freight
            gst = taxable * (self._party_gst_rate / 100)

            header = {
                "company_id":     state.company_id,
                "invoice_no":     inv_no,
                "invoice_date":   self.inv_date.value,
                "party_id":       self.party_dd.value,
                "agent_id":       self.agent_dd.value,
                "transporter_id": self.trans_dd.value,
                "destination":    self.dest.value,
                "order_by":       self.order_by.value,
                "order_thro":     self.order_thro.value,
                "qty_type":       self.qty_type.value,
                "lr_no":          self.lr_no.value,
                "lr_date":        self.lr_date.value,
                "no_case":        int(self.no_cases.value or 0),
                "case_no":        self.case_no.value,
                "tot_weight":     float(self.weight.value or 0),
                "charges":        freight,
                "total_pcs":      int(total_pcs),
                "total_boxes":    round(total_boxes, 2),
                "total_amount":   round(gross, 2),
                "td_percent":     0,
                "spd_percent":    0,
                "festival_percent": 0,
                "scd_percent":    0,
                "cd_percent":     0,
                "tax_type":       self._party_tax_type,
                "tax_per":        self._party_gst_rate,
                "gst_amount":     round(gst, 2),
                "round_off":      float(self.round_off.value or 0),
                "net_amount":     round(taxable + gst + float(self.round_off.value or 0), 2),
                "status":         "Unbilled"
            }
            
            res = insert("transport_invoices", header)
            if not res: raise Exception("Failed to save invoice header")
            ti_id = res[0]["id"]
            
            # Fetch company and party details for PDF
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            party_data = select("parties", {"id": self.party_dd.value})
            party = party_data[0] if party_data else {}
            header["party_name"] = party.get("name", "Customer")
            header["party_address"] = f"{party.get('billing_address_line1','')}, {party.get('city','')}"
            header["party_gstin"] = party.get("gstin", "-")
            header["taxable_amount"] = taxable

            # Link slips and move items
            all_items_for_pdf = []
            for s in selected_data:
                sid = str(s["id"])
                items = select("packing_slip_items", {"packing_slip_id": sid})
                for it in items:
                    # Resolve item name if missing
                    if not it.get("item_name"):
                        i_data = select("items", {"id": it["item_id"]})
                        it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"
                    
                    row = {
                        "company_id":           state.company_id,
                        "transport_invoice_id": ti_id,
                        "packing_slip_id":      sid,
                        "item_id":              it["item_id"],
                        "item_name":            it["item_name"],
                        "size_value":           it["size_value"],
                        "rate":                 it["rate"],
                        "qty_pieces":           it["qty_pieces"],
                        "qty_boxes":            it["qty_boxes"],
                        "amount":               it["amount"]
                    }
                    insert("transport_invoice_items", row)
                    all_items_for_pdf.append(row)
                update("packing_slips", {"status": "Billed"}, {"id": sid})

            # Generate PDF
            pdf_path = pdf_engine.generate_tax_invoice(header, all_items_for_pdf, company)
            print_pdf(pdf_path)

            self._snack(f"✅ Invoice {inv_no} generated!", "green")
            self.clear_form()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def clear_form(self):
        self.inv_no.value = f"TI-{uuid.uuid4().hex[:6].upper()}"
        self.lr_no.value = ""
        self.no_cases.value = "0"
        self.weight.value = "0"
        self.charges.value = "0"
        self._selected_slips.clear()
        self._available_slips = []
        self.items_col.controls = []
        self.party_dd.value = None
        self._calc()
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # History & Printing
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        invs = select("transport_invoices", {"company_id": state.company_id})
        invs.sort(key=lambda x: x.get("invoice_date", ""), reverse=True)
        
        parties = select("parties", {"company_id": state.company_id})
        party_map = {str(p["id"]): p["name"] for p in parties}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for inv in invs:
            p_name = party_map.get(str(inv.get("party_id")), "Unknown")
            inv["party_name"] = p_name
            
            lv.controls.append(
                ft.Container(
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{inv.get('invoice_no')}  |  {inv.get('invoice_date')}", weight="bold", size=14),
                            ft.Text(f"Created: {(inv.get('created_at') or '').replace('T', ' ')[:16]}", size=10, color=ft.colors.BLUE_GREY_400),
                            ft.Text(p_name, size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"Pcs: {inv.get('total_pcs', 0)}", size=12),
                        ft.Text(f"₹ {float(inv.get('net_amount', 0)):,.2f}", size=14, weight="bold", color=AppColors.PRIMARY),
                        ft.IconButton(ft.icons.PRINT, tooltip="Print Invoice", icon_color=ft.colors.BLUE_700, 
                                      on_click=lambda e, i=inv: self.print_history_invoice(i))
                    ])
                )
            )
            
        dlg = ft.AlertDialog(
            title=ft.Text("Recent Transport Invoices"),
            content=ft.Container(width=600, height=400, content=lv),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def print_history_invoice(self, invoice):
        try:
            items = select("transport_invoice_items", {"invoice_id": invoice["id"]})
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            pdf_path = pdf_engine.generate_tax_invoice(invoice, items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing: {ex}", "red")
