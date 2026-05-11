import flet as ft
import uuid
import math
import os
import json
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
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
        self.current_edit_id  = None

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
        self.price_list = ft.Dropdown(label="Price List",   width=150, **S)
        self.qty_type   = ft.TextField(label="Qty Type",    width=100, **S)
        
        # ── LR Details ──────────
        self.lr_no      = ft.TextField(label="LR No",     width=120, **S)
        self.lr_date    = ft.TextField(label="LR Date",   width=120, value=date.today().isoformat(), **S)
        self.no_cases   = ft.TextField(label="No of Cases", width=100, value="0", **S)
        self.case_no    = ft.TextField(label="Case No",    width=120, **S)
        self.weight     = ft.TextField(label="Tot Weight", width=100, value="0", **S)
        self.charges    = ft.TextField(label="Transport/Freight", width=130, value="0", on_change=self._calc, **S)

        # ── Footer Totals ────────────────────────────────────
        self.no_of_items_lbl = ft.Text("No. Of Items: 0", size=13, weight="bold")
        self.total_pcs   = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        self.total_boxes = ft.Text("Total Boxes: 0",  size=13, weight="bold")
        
        self.taxable_val = ft.Text("Taxable: ₹0.00", size=14, weight="bold")
        
        # Detailed Tax Fields
        self.tax_type_dd = ft.Dropdown(
            label="Tax Type",
            options=[ft.dropdown.Option("GST"), ft.dropdown.Option("IGST")],
            value="GST",
            width=120,
            on_change=self._calc
        )
        self.gst_rate_tf = ft.TextField(label="GST %", value="5", width=60, on_change=self._calc, **S)
        self.cgst_rate_tf = ft.TextField(label="CGST %", value="0", width=60, on_change=self._calc, **S)
        self.cgst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.sgst_rate_tf = ft.TextField(label="SGST %", value="0", width=60, on_change=self._calc, **S)
        self.sgst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.igst_rate_tf = ft.TextField(label="IGST %", value="0", width=60, on_change=self._calc, visible=False, **S)
        self.igst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB, visible=False)
        
        self.cess_rate_tf = ft.TextField(label="Cess %", value="0", width=60, on_change=self._calc, **S)
        self.cess_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.tcs_rate_tf = ft.TextField(label="TCS %",  value="0", width=60, on_change=self._calc, **S)
        self.tcs_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)

        self.trade_disc   = ft.TextField(label="Trade %",  value="0", width=80, on_change=self._calc, **S)
        self.td_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.scheme_disc  = ft.TextField(label="Scheme %", value="0", width=80, on_change=self._calc, **S)
        self.spd_amt_lbl  = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.fest_disc    = ft.TextField(label="Fest %",   value="0", width=80, on_change=self._calc, **S)
        self.fd_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.spec_disc    = ft.TextField(label="Spec %",   value="0", width=80, on_change=self._calc, **S)
        self.scd_amt_lbl  = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.cash_disc    = ft.TextField(label="Cash %",   value="0", width=80, on_change=self._calc, **S)
        self.cd_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        # --- Dynamic discount ordering ---
        self.DEFAULT_DISCOUNT_ORDER = ["trade", "scheme", "festival", "scd", "cd"]
        self.DISCOUNT_MAP = {
            "trade":    {"field": self.trade_disc,  "amt": self.td_amt_lbl},
            "scheme":   {"field": self.scheme_disc, "amt": self.spd_amt_lbl},
            "festival": {"field": self.fest_disc,   "amt": self.fd_amt_lbl},
            "scd":      {"field": self.spec_disc,   "amt": self.scd_amt_lbl},
            "cd":       {"field": self.cash_disc,   "amt": self.cd_amt_lbl},
        }
        self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self.discount_row = ft.Row(spacing=15)
        self._reorder_discount_fields()

        self.gst_lbl     = ft.Text("GST: ₹0.00", size=13, color=AppColors.TEXT_SUB)
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
                ft.Checkbox(on_change=self.toggle_all, tooltip="Select All"),
                ft.Text("SLIP NO",   width=120, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("DATE",      width=100, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("ITEMS",     width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("PCS",       width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("BOXES",     width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("AMOUNT",    expand=True, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
            ]),
        )

    def _reorder_discount_fields(self):
        self.discount_row.controls = []
        for key in self._discount_order:
            meta = self.DISCOUNT_MAP.get(key)
            if meta:
                self.discount_row.controls.append(
                    ft.Column([meta["field"], meta["amt"]],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
                )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Column([
                # Row 1: Totals and Discounts
                ft.Row([
                    ft.Column([
                        self.no_of_items_lbl,
                        ft.Row([self.total_pcs, ft.Text(" | "), self.total_boxes], spacing=10),
                    ], spacing=5),
                    ft.Container(expand=True),
                    self.discount_row,
                ]),
                
                ft.Divider(height=1, color="#E2E8F0"),
                
                # Row 2: Tax Breakup and Actions
                ft.Row([
                    ft.Column([
                        self.taxable_val,
                        ft.Row([
                            self.tax_type_dd,
                            self.gst_rate_tf,
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.cgst_rate_tf, self.cgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([self.sgst_rate_tf, self.sgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([self.igst_rate_tf, self.igst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.cess_rate_tf, self.cess_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([self.tcs_rate_tf,  self.tcs_amt_lbl],  spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            self.gst_lbl,
                        ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=2, expand=True),

                    ft.VerticalDivider(width=1, color="#E2E8F0"),

                    # Round Off Section
                    ft.Column([
                        self.round_off,
                        ft.Row([
                            ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.did_mount(), tooltip="Refresh Data", icon_size=16),
                            ft.Text("Refresh", size=10, color=AppColors.TEXT_SUB),
                        ], spacing=0),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),

                    ft.Container(width=20),

                    # Grand Total Section
                    ft.Column([
                        ft.Text("Grand Total", size=11, color=AppColors.TEXT_SUB, weight="w500"),
                        self.net_amt,
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),

                    ft.Container(width=10),

                    ft.ElevatedButton(
                        "Generate Invoice",
                        icon=ft.icons.RECEIPT_LONG,
                        on_click=self.save_invoice,
                        height=48,
                        style=AppStyles.primary_button_style(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=12),
        )

    def did_mount(self):
        self.load_dropdowns()
        if not self.inv_no.value:
            self.inv_no.value = get_next_doc_no("transport_invoices", "T", state.company_id, "invoice_no")

    def load_dropdowns(self):
        if not state.company_id: return
        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Customer", "Both"]})
        agents       = select("agents",       {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        
        price_lists  = select("price_lists",  {"company_id": state.company_id})
        
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        self.price_list.options = [ft.dropdown.Option(key=str(p["id"]), text=p["list_name"]) for p in price_lists]
        
        if self.page: self.update()

    def on_party_change(self, e):
        party_id = self.party_dd.value
        if not party_id: return
        pdata = select("parties", {"id": party_id})
        if pdata:
            p = pdata[0]
            self.dest.value   = p.get("delivery_city") or p.get("billing_city", "")
            if p.get("agent_id"):       self.agent_dd.value   = str(p["agent_id"])
            if p.get("transporter_id"): self.trans_dd.value   = str(p["transporter_id"])
            if p.get("price_list_id"):  self.price_list.value = str(p["price_list_id"])
            # Initial default, but will be overridden by slip selection
            self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type = p.get("tax_type", "IGST") or "IGST"
        
        self.load_slips(party_id)



    def load_slips(self, party_id):
        if not party_id:
            self._available_slips = []
            self.rebuild_grid()
            return

        # 1. Fetch all Unbilled slips
        slips = select("packing_slips", {
            "party_id": party_id, 
            "company_id": state.company_id,
            "status": "Unbilled"
        })
        
        # 2. If editing, also fetch slips ALREADY in this transport invoice
        if self.current_edit_id:
            items = select("transport_invoice_items", {"transport_invoice_id": self.current_edit_id})
            linked_ids = [str(it["packing_slip_id"]) for it in items if it.get("packing_slip_id")]
            if linked_ids:
                linked_slips = select("packing_slips", {"id": linked_ids})
                # Merge and avoid duplicates
                existing_ids = {str(s["id"]) for s in slips}
                for ls in linked_slips:
                    if str(ls["id"]) not in existing_ids:
                        slips.append(ls)
        
        self._available_slips = slips
        self.rebuild_grid()

    def toggle_all(self, e):
        if e.control.value:
            self._selected_slips = {str(s["id"]) for s in self._available_slips}
        else:
            self._selected_slips.clear()
        self.rebuild_grid()

    def on_slip_toggle(self, slip_id, val):
        if val: 
            if not self._selected_slips:
                # Inherit from the first one selected
                s = next((x for x in self._available_slips if str(x["id"]) == slip_id), None)
                if s:
                    self.tax_type_dd.value  = s.get("tax_type", "GST")
                    self.trade_disc.value   = str(s.get("td_percent") or 0)
                    self.scheme_disc.value  = str(s.get("spd_percent") or 0)
                    self.fest_disc.value    = str(s.get("festival_percent") or 0)
                    self.spec_disc.value    = str(s.get("scd_percent") or 0)
                    self.cash_disc.value    = str(s.get("cd_percent") or 0)
                    
                    rate = float(s.get("tax_per", 5) or 5)
                    if self.tax_type_dd.value == "IGST":
                        self.igst_rate_tf.value = str(rate)
                        self.cgst_rate_tf.value = "0"
                        self.sgst_rate_tf.value = "0"
                    else:
                        self.cgst_rate_tf.value = str(rate/2)
                        self.sgst_rate_tf.value = str(rate/2)
                        self.igst_rate_tf.value = "0"

            self._selected_slips.add(slip_id)
        else: 
            self._selected_slips.discard(slip_id)
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
        trigger = e.control if e and hasattr(e, "control") else e if isinstance(e, ft.Control) else None

        # 1. Sync CGST/SGST if GST rate changed or mode switched
        if trigger == self.gst_rate_tf or trigger == self.tax_type_dd:
            try:
                val_str = str(self.gst_rate_tf.value or "").strip()
                if val_str.endswith("."): gst_p = float(val_str + "0")
                else: gst_p = float(val_str or 0)
                
                if self.tax_type_dd.value == "GST":
                    self.cgst_rate_tf.value = f"{gst_p/2:g}"
                    self.sgst_rate_tf.value = f"{gst_p/2:g}"
                else:
                    self.igst_rate_tf.value = f"{gst_p:g}"
            except: pass
        total_pcs = total_boxes = gross = 0.0
        selected_data = [s for s in self._available_slips if str(s["id"]) in self._selected_slips]
        
        for s in selected_data:
            total_pcs   += float(s.get("total_pcs", 0))
            total_boxes += float(s.get("total_boxes", 0))
            
            # Recalculate Gross from scratch by summing items
            items = select("packing_slip_items", {"packing_slip_id": s["id"]})
            gross += sum(float(it.get("qty_pieces", 0)) * float(it.get("rate", 0)) for it in items)

        try:
            freight_val = float(self.charges.value or 0)
            
            # 1. Base -> Sequential Discounts = Discounted Total
            running_total = gross
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    try:
                        d = float(meta["field"].value or 0)
                        disc_amt = running_total * (d / 100)
                        meta["amt"].value = f"Amt: ₹{disc_amt:,.2f}"
                        running_total -= disc_amt
                    except: pass
            
            # 2. Add Freight to get Taxable Base
            taxable = running_total + freight_val
            
            # Breakdown tax fields
            tax_type = self.tax_type_dd.value
            cgst_rate = float(self.cgst_rate_tf.value or 0)
            sgst_rate = float(self.sgst_rate_tf.value or 0)
            igst_rate = float(self.igst_rate_tf.value or 0)
            cess_rate = float(self.cess_rate_tf.value or 0)
            tcs_rate  = float(self.tcs_rate_tf.value or 0)

            total_gst = 0
            if selected_data:
                # Calculate GST on discounted taxable
                pass

            cgst_amt = taxable * (cgst_rate / 100) if tax_type == "GST" else 0
            sgst_amt = taxable * (sgst_rate / 100) if tax_type == "GST" else 0
            igst_amt = taxable * (igst_rate / 100) if tax_type == "IGST" else 0
            cess_amt = taxable * (cess_rate / 100)
            
            # Total GST
            gst = cgst_amt + sgst_amt + igst_amt
            if not gst and selected_data:
                # Fallback to inherited GST (scaled by discounts)
                for s in selected_data:
                    items = select("packing_slip_items", {"packing_slip_id": s["id"]})
                    for it in items:
                        item_amt = float(it.get("amount", 0))
                        # Scale factor
                        if (gross + freight_val) > 0:
                            scale = taxable / (gross + freight_val)
                            total_gst += (item_amt * scale) * (float(it.get("tax_percent", 5) or 5) / 100)
                
                # GST on freight (also scaled)
                header_rate = float(selected_data[0].get("tax_per", 5) or 5)
                if (gross + freight_val) > 0:
                    scale = taxable / (gross + freight_val)
                    total_gst += (freight_val * scale) * (header_rate / 100)
                gst = total_gst

            tcs_amt  = (taxable + gst) * (tcs_rate / 100)
            
            self.cgst_amt_lbl.value = f"Amt: ₹{cgst_amt:,.2f}"
            self.sgst_amt_lbl.value = f"Amt: ₹{sgst_amt:,.2f}"
            self.igst_amt_lbl.value = f"Amt: ₹{igst_amt:,.2f}"
            self.cess_amt_lbl.value = f"Amt: ₹{cess_amt:,.2f}"
            self.tcs_amt_lbl.value  = f"Amt: ₹{tcs_amt:,.2f}"
            
            # Visibilities
            self.igst_rate_tf.visible = self.igst_amt_lbl.visible = (tax_type == "IGST")
            self.cgst_rate_tf.visible = self.cgst_amt_lbl.visible = (tax_type == "GST")
            self.sgst_rate_tf.visible = self.sgst_amt_lbl.visible = (tax_type == "GST")

            gst = total_gst
            if not gst and (cgst_amt or igst_amt):
                 gst = cgst_amt + sgst_amt + igst_amt

            subtotal = taxable + gst + cess_amt + tcs_amt
            final_amt = math.ceil(subtotal)
            roff = final_amt - subtotal
            
            self.total_pcs.value   = f"Total Pcs: {int(total_pcs)}"
            self.total_boxes.value = f"Total Boxes: {total_boxes:.1f}"
            self.no_cases.value    = str(math.ceil(total_boxes))
            self.taxable_val.value = f"Taxable: ₹{taxable:,.2f}"
            self.gst_lbl.value     = f"{tax_type}: ₹{gst:,.2f}"
            self.round_off.value   = f"{roff:.2f}"
            self.net_amt.value     = f"Total: ₹{final_amt:,.2f}"
        except Exception: pass
        except Exception: pass
        if self.page: self.update()

    def save_invoice(self, e):
        if not self.party_dd.value or not self._selected_slips:
            self._snack("Select party and at least one slip!", "red")
            return
        
        if not self.tax_type_dd.value:
            self._snack("Please select a Tax Type (GST/IGST) before saving!", "red")
            return
        
        try:
            inv_no = self.inv_no.value or f"TI-{uuid.uuid4().hex[:6].upper()}"
            selected_data = [s for s in self._available_slips if str(s["id"]) in self._selected_slips]
            
            total_pcs = sum(float(s.get("total_pcs", 0)) for s in selected_data)
            total_boxes = sum(float(s.get("total_boxes", 0)) for s in selected_data)
            
            # Recalculate Gross from scratch for saving
            gross = 0
            for s in selected_data:
                items = select("packing_slip_items", {"packing_slip_id": s["id"]})
                gross += sum(float(it.get("qty_pieces", 0)) * float(it.get("rate", 0)) for it in items)
            
            freight_val = float(self.charges.value or 0)

            # Apply Sequential Discounts to Gross ONLY (Freight excluded)
            running_total = gross
            discs = {}
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    try:
                        d = float(meta["field"].value or 0)
                        da = running_total * (d / 100)
                        discs[key] = {"p": d, "a": da}
                        running_total -= da
                    except: pass
            
            taxable = running_total + freight_val
            tax_type = self.tax_type_dd.value
            cgst_rate = float(self.cgst_rate_tf.value or 0)
            sgst_rate = float(self.sgst_rate_tf.value or 0)
            igst_rate = float(self.igst_rate_tf.value or 0)
            cess_rate = float(self.cess_rate_tf.value or 0)
            tcs_rate  = float(self.tcs_rate_tf.value or 0)
            
            # Sequence calculation (mirrors _calc)
            running_total = gross + freight_val
            discs = {}
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    d = float(meta["field"].value or 0)
                    amt = running_total * (d / 100)
                    discs[key] = {"p": d, "a": amt}
                    running_total -= amt
            
            taxable = running_total
            cgst_amt = taxable * (cgst_rate / 100) if tax_type == "GST" else 0
            sgst_amt = taxable * (sgst_rate / 100) if tax_type == "GST" else 0
            igst_amt = taxable * (igst_rate / 100) if tax_type == "IGST" else 0
            cess_amt = taxable * (cess_rate / 100)
            gst = cgst_amt + sgst_amt + igst_amt
            
            # Fallback to inherited GST
            if not gst and selected_data:
                total_gst = 0
                for s in selected_data:
                    items = select("packing_slip_items", {"packing_slip_id": s["id"]})
                    for it in items:
                        item_amt = float(it.get("amount", 0))
                        if (gross + freight_val) > 0:
                            scale = taxable / (gross + freight_val)
                            total_gst += (item_amt * scale) * (float(it.get("tax_percent", 5) or 5) / 100)
                
                header_rate = float(selected_data[0].get("tax_per", 5) or 5)
                if (gross + freight_val) > 0:
                    scale = taxable / (gross + freight_val)
                    total_gst += (freight_val * scale) * (header_rate / 100)
                gst = total_gst

            tcs_amt = (taxable + gst) * (tcs_rate / 100)
            roff = float(self.round_off.value or 0)
            net = round(taxable + gst + cess_amt + tcs_amt + roff, 0)

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
                "price_list_id":  self.price_list.value,
                "qty_type":       self.qty_type.value,
                "lr_no":          self.lr_no.value,
                "lr_date":        self.lr_date.value,
                "no_case":        int(self.no_cases.value or 0),
                "case_no":        self.case_no.value,
                "tot_weight":     float(self.weight.value or 0),
                "charges":        freight_val,
                "total_pcs":      int(total_pcs),
                "total_boxes":    round(total_boxes, 2),
                "total_amount":   round(taxable, 2),
                "td_percent":     discs.get("trade", {}).get("p", 0),
                "td_amount":      round(discs.get("trade", {}).get("a", 0), 2),
                "spd_percent":    discs.get("scheme", {}).get("p", 0),
                "spd_amount":     round(discs.get("scheme", {}).get("a", 0), 2),
                "festival_percent": discs.get("festival", {}).get("p", 0),
                "festival_amount":  round(discs.get("festival", {}).get("a", 0), 2),
                "scd_percent":    discs.get("scd", {}).get("p", 0),
                "scd_amount":     round(discs.get("scd", {}).get("a", 0), 2),
                "cd_percent":     discs.get("cd", {}).get("p", 0),
                "cd_amount":      round(discs.get("cd", {}).get("a", 0), 2),
                "tax_type":       tax_type,
                "tax_per":        igst_rate if tax_type == "IGST" else cgst_rate * 2,
                "gst_amount":     round(gst + cess_amt, 2),
                "tcs_amount":     round(tcs_amt, 2),
                "round_off":      round(roff, 2),
                "net_amount":     net,
                "status":         "Unbilled"
            }
            
            res = None
            if self.current_edit_id:
                ti_id = self.current_edit_id
                # 1. Identify and restore previous slips to "Unbilled"
                prev_items = select("transport_invoice_items", {"transport_invoice_id": ti_id})
                prev_slip_ids = {str(it["packing_slip_id"]) for it in prev_items if it.get("packing_slip_id")}
                for psid in prev_slip_ids:
                    update("packing_slips", {"status": "Unbilled"}, {"id": psid})

                # 2. Update header and clear items for replacement
                update("transport_invoices", header, {"id": ti_id})
                delete("transport_invoice_items", {"transport_invoice_id": ti_id})
            else:
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

            # Collect unique internal order numbers for the PDF header
            unique_orders = set()
            for it in all_items_for_pdf:
                oid = it.get("order_id")
                if not oid: # Need to fetch from packing_slip_items if not in TI items
                    ps_item = select("packing_slip_items", {"packing_slip_id": it["packing_slip_id"], "item_id": it["item_id"], "size_value": it["size_value"]})
                    if ps_item: oid = ps_item[0].get("order_id")
                
                if oid:
                    o_data = select("orders", {"id": oid})
                    if o_data: unique_orders.add(o_data[0].get("order_no", "ORD"))
            header["order_no"] = ", ".join(sorted(list(unique_orders)))

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
        self.inv_no.value = get_next_doc_no("transport_invoices", "T", state.company_id, "invoice_no")
        self.lr_no.value = ""
        self.no_cases.value = "0"
        self.weight.value = "0"
        self.charges.value = "0"
        self._selected_slips.clear()
        self._available_slips = []
        self.items_col.controls = []
        self.party_dd.value = None
        self.current_edit_id = None
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
                        ft.Row([
                            ft.IconButton(ft.icons.EDIT_OUTLINED, tooltip="Edit Invoice", icon_color=AppColors.PRIMARY,
                                          on_click=lambda e, i=inv: self.load_invoice_for_edit(i, dlg)),
                            ft.IconButton(ft.icons.PRINT, tooltip="Print Invoice", icon_color=ft.colors.BLUE_700, 
                                          on_click=lambda e, i=inv: self.print_history_invoice(i)),
                            ft.IconButton(ft.icons.DELETE_OUTLINE, tooltip="Delete Invoice", icon_color="red",
                                          on_click=lambda e, i=inv: self.delete_invoice_from_history(i, dlg))
                        ])
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

    def load_invoice_for_edit(self, invoice, dlg):
        """Loads a past transport invoice into the main form for editing."""
        try:
            self._close_dialog(dlg)
            self.clear_form()
            
            self.current_edit_id  = invoice["id"]
            self.inv_no.value     = invoice.get("invoice_no", "")
            self.inv_date.value   = invoice.get("invoice_date", "")
            self.party_dd.value   = str(invoice.get("party_id")) if invoice.get("party_id") else None
            self.agent_dd.value   = str(invoice.get("agent_id")) if invoice.get("agent_id") else None
            self.trans_dd.value   = str(invoice.get("transporter_id")) if invoice.get("transporter_id") else None
            self.dest.value       = invoice.get("destination", "")
            self.order_by.value   = invoice.get("order_by", "")
            self.order_thro.value = invoice.get("order_thro", "")
            self.price_list.value = invoice.get("price_list", "")
            self.qty_type.value   = invoice.get("qty_type", "")
            self.lr_no.value      = invoice.get("lr_no", "")
            self.lr_date.value    = invoice.get("lr_date", "")
            self.no_cases.value   = str(invoice.get("no_case", 0))
            self.case_no.value    = invoice.get("case_no", "")
            self.weight.value     = str(invoice.get("tot_weight", 0))
            self.charges.value    = str(invoice.get("charges", 0))
            self.price_list.value = str(invoice.get("price_list_id")) if invoice.get("price_list_id") else None
            self.round_off.value  = str(invoice.get("round_off", "0.00"))
            
            # Tax & Discounts
            self.tax_type_dd.value = invoice.get("tax_type", "GST")
            rate = float(invoice.get("tax_per", 5) or 5)
            if self.tax_type_dd.value == "IGST":
                self.igst_rate_tf.value = str(rate)
            else:
                self.cgst_rate_tf.value = str(rate/2)
                self.sgst_rate_tf.value = str(rate/2)

            self.trade_disc.value  = str(invoice.get("td_percent", 0))
            self.scheme_disc.value = str(invoice.get("spd_percent", 0))
            self.fest_disc.value   = str(invoice.get("festival_percent", 0))
            self.spec_disc.value   = str(invoice.get("scd_percent", 0))
            self.cash_disc.value   = str(invoice.get("cd_percent", 0))

            # Load party GST info
            if self.party_dd.value:
                pdata = select("parties", {"id": self.party_dd.value})
                if pdata:
                    p = pdata[0]
                    self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
                    self._party_tax_type = p.get("tax_type", "IGST") or "IGST"

            # Load slips (this now fetches both unbilled and already linked ones)
            self.load_slips(self.party_dd.value)
            
            # Pre-select the ones that were in the invoice
            db_items = select("transport_invoice_items", {"transport_invoice_id": invoice["id"]})
            self._selected_slips = {str(it["packing_slip_id"]) for it in db_items if it.get("packing_slip_id")}
            
            self.rebuild_grid()
            self._calc() # Force UI to split CGST/SGST
            self._snack(f"Loaded Invoice: {self.inv_no.value}", AppColors.PRIMARY)
        except Exception as ex:
            print(f"Edit Load Error: {ex}")
            self._snack(f"Failed to load invoice: {ex}", "red")

    def delete_invoice_from_history(self, invoice, dlg):
        """Deletes a transport invoice and restores packing slip status."""
        def confirm_delete(e):
            try:
                # Check if billed in a final invoice
                # We check the final_invoices table for any record referencing this TI
                linked = select("final_invoices", {"transport_invoice_id": invoice["id"]})
                if linked or invoice.get("status") == "Invoiced":
                    confirm_dlg.open = False
                    self.page.update()
                    self._snack("Cannot delete: This invoice is already included in a Sales Tax Invoice. Delete the Sales Invoice first.", "orange")
                    return

                # 1. Identify associated packing slips
                items = select("transport_invoice_items", {"transport_invoice_id": invoice["id"]})
                slip_ids = {str(it["packing_slip_id"]) for it in items if it.get("packing_slip_id")}
                
                # 2. Restore Packing Slips to "Unbilled"
                for sid in slip_ids:
                    update("packing_slips", {"status": "Unbilled"}, {"id": sid})

                # 3. Delete items and header
                delete("transport_invoice_items", {"transport_invoice_id": invoice["id"]})
                delete("transport_invoices", {"id": invoice["id"]})
                
                confirm_dlg.open = False
                dlg.open = False
                self.page.update()
                self._snack(f"Invoice {invoice.get('invoice_no')} deleted.", "green")
                self.show_history_modal(None)
            except Exception as ex:
                self._snack(f"Delete Error: {ex}", "red")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete transport invoice {invoice.get('invoice_no')}?"),
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
