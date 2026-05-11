import flet as ft
import uuid
import math
import os
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
from core.pdf_gen import pdf_engine, print_pdf

class SalesInvoiceTab(ft.Column):
    """
    Sales Invoice (The final GST-compliant Tax Invoice)
    - Pulls 'Unbilled' Transport Invoices
    - Finalizes tax breakup (CGST/SGST or IGST)
    - Mandatory LR details (for E-way bill compliance)
    """

    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        self._available_invoices = []
        self._selected_inv_ids   = set()
        self._party_gst_rate     = 5.0
        self._party_tax_type     = "IGST"
        self.current_edit_id     = None

        # ── Header ───────────────────────────────────────────
        S = AppStyles.get_input_style()
        self.inv_no    = ft.TextField(label="Tax Invoice No", width=160, **S)
        self.inv_date  = ft.TextField(label="Invoice Date",   width=140, value=date.today().isoformat(), **S)
        self.party_dd  = ft.Dropdown(label="Select Party *",  width=280, on_change=self.on_party_change, **S)
        
        # Consistent fields
        self.agent_dd   = ft.Dropdown(label="Agent",       width=160, **S)
        self.trans_dd   = ft.Dropdown(label="Transporter", width=180, **S)
        self.dest       = ft.TextField(label="Destination",width=150, **S)
        self.order_by   = ft.TextField(label="Order By",    width=130, **S)
        self.order_thro = ft.TextField(label="Order Thro'", width=130, **S)
        self.qty_type   = ft.TextField(label="Qty Type",    width=100, **S)
        
        # LR/Freight details
        self.lr_no   = ft.TextField(label="LR No",   width=120, **S)
        self.lr_date = ft.TextField(label="LR Date", width=120, value=date.today().isoformat(), **S)
        self.freight = ft.TextField(label="Freight", value="0", width=100, on_change=self._calc, **S)
        self.other   = ft.TextField(label="Other Exp", value="0", width=100, on_change=self._calc, **S)

        # ── Footer Totals ────────────────────────────────────
        self.no_of_items_lbl = ft.Text("No. Of Items: 0", size=13, weight="bold")
        self.total_pcs   = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        self.total_amt   = ft.Text("Base Amount: ₹0.00", size=14, weight="bold")
        
        # Tax Breakup
        self.taxable_val = ft.Text("Taxable: ₹0.00", size=16, weight="bold")
        
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

        self.cgst_lbl    = ft.Text("CGST: ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.sgst_lbl    = ft.Text("SGST: ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.igst_lbl    = ft.Text("IGST: ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.round_off   = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self._calc, **S)
        self.net_amt     = ft.Text("Total: ₹0.00", size=24, weight="bold", color=AppColors.PRIMARY)

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
                        ft.Text("Sales Tax Invoice", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15),
                    ft.Row([self.inv_no, self.inv_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Party and Logistic Info
                ft.Row([
                    self.party_dd, self.agent_dd, self.trans_dd, self.dest,
                ], spacing=12, wrap=True),
                
                # Row 3: Order details
                ft.Row([
                    self.order_by, self.order_thro, self.qty_type,
                ], spacing=12, wrap=True),

                # Row 4: LR & Charges
                ft.Row([
                    self.lr_no, self.lr_date,
                    ft.VerticalDivider(width=20),
                    self.freight, self.other
                ], spacing=12, wrap=True),
            ], spacing=15),
        )

    def _build_col_header(self):
        return ft.Container(
            bgcolor="#F1F5F9",
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            content=ft.Row([
                ft.Checkbox(on_change=self.toggle_all, tooltip="Select All"),
                ft.Text("TRANS INV NO", width=140, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("LR NO",       width=100, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("LR DATE",     width=100, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("CASES",      width=60,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("PCS",        width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("TAXABLE",    expand=True, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
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
                        ft.Row([self.total_pcs, ft.Text(" | "), self.total_amt], spacing=10),
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
                            ft.Column([self.cgst_lbl, self.sgst_lbl, self.igst_lbl], spacing=2),
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
                        "Confirm & Save Invoice",
                        icon=ft.icons.CHECK_CIRCLE,
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
            self.inv_no.value = get_next_doc_no("final_invoices", "S", state.company_id, "invoice_no")

    def load_dropdowns(self):
        if not state.company_id: return
        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Customer", "Both"]})
        agents       = select("agents",       {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        
        if not self.inv_no.value:
            self.inv_no.value = get_next_doc_no("final_invoices", "S", state.company_id, "invoice_no")
            
        if self.page: self.update()

    def on_party_change(self, e):
        party_id = self.party_dd.value
        if not party_id: return
        pdata = select("parties", {"id": party_id})
        if pdata:
            p = pdata[0]
            self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type = p.get("tax_type", "IGST") or "IGST"
        
        self.load_invoices(party_id)

    def load_invoices(self, party_id):
        direct_mode = state.settings.get("direct_invoice", False)
        
        if direct_mode:
            # Pull orders that aren't fully invoiced yet
            # In a real app, you'd track 'invoiced_status'. For now, pull Pending/Partial.
            self._available_invoices = select("orders", {
                "party_id": party_id, 
                "company_id": state.company_id
            })
            # Filter for non-completed in Python for simplicity
            self._available_invoices = [o for o in self._available_invoices if o.get("status") != "Completed"]
        else:
            self._available_invoices = select("transport_invoices", {
                "party_id": party_id, 
                "company_id": state.company_id,
                "status": "Unbilled"
            })
        
        self._selected_inv_ids.clear()
        self.rebuild_grid()

    def toggle_all(self, e):
        if e.control.value:
            self._selected_inv_ids = {str(s["id"]) for s in self._available_invoices}
        else:
            self._selected_inv_ids.clear()
        self.rebuild_grid()

    def on_inv_toggle(self, inv_id, val):
        if val: 
            if not self._selected_inv_ids:
                # Inherit from the first one selected
                s = next((x for x in self._available_invoices if str(x["id"]) == inv_id), None)
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

            self._selected_inv_ids.add(inv_id)
        else: 
            self._selected_inv_ids.discard(inv_id)
        self._calc()

    def rebuild_grid(self):
        self.items_col.controls = []
        direct_mode = state.settings.get("direct_invoice", False)
        
        if not self._available_invoices:
            msg = "No pending orders found." if direct_mode else "No pending transport invoices."
            self.items_col.controls = [ft.Container(padding=40, content=ft.Text(msg, color="#999"))]
        else:
            for s in self._available_invoices:
                sid = str(s["id"])
                
                if direct_mode:
                    # For orders, total_amount is the base
                    display_no = s.get("order_no", "-")
                    col2 = s.get("order_date", "-")
                    col3 = "" # No LR in order
                    col4 = "" # No LR Date
                    pcs = s.get("total_pcs", 0)
                    taxable = float(s.get("total_amount", 0))
                else:
                    display_no = s.get("invoice_no", "-")
                    col2 = s.get("lr_no", "-")
                    col3 = s.get("lr_date", "-")
                    col4 = str(s.get("no_case", 0))
                    pcs = s.get("total_pcs", 0)
                    net = float(s.get("net_amount", 0))
                    rate = float(s.get("tax_per", 5))
                    taxable = net / (1 + rate/100)
                
                self.items_col.controls.append(
                    ft.Container(
                        bgcolor=ft.colors.WHITE,
                        padding=ft.padding.symmetric(horizontal=24, vertical=12),
                        border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
                        content=ft.Row([
                            ft.Checkbox(value=(sid in self._selected_inv_ids), on_change=lambda e, sid=sid: self.on_inv_toggle(sid, e.control.value)),
                            ft.Text(display_no, width=140, size=13, weight="bold"),
                            ft.Text(col2, width=100, size=13),
                            ft.Text(col3, width=100, size=13),
                            ft.Text(col4, width=60, size=13, text_align=ft.TextAlign.RIGHT),
                            ft.Text(str(pcs), width=80, size=13, text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"₹{taxable:,.2f}", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY),
                        ])
                    )
                )
        self._calc()
        if self.page: self.update()

    def _calc(self, e=None):
        trigger = e.control if e and hasattr(e, "control") else e if isinstance(e, ft.Control) else None
        
        selected_data = [s for s in self._available_invoices if str(s["id"]) in self._selected_inv_ids]
        direct_mode = state.settings.get("direct_invoice", False)

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

        # Mandate 2025/2026:
        if selected_data and trigger != self.gst_rate_tf:
             # We check the rates of items in selected invoices
             mandated_rate = 5.0
             curr_val = float(self.gst_rate_tf.value or 0)
             if curr_val == 0:
                self.gst_rate_tf.value = "5" # Default
                if self.tax_type_dd.value == "GST":
                    self.cgst_rate_tf.value = "2.5"
                    self.sgst_rate_tf.value = "2.5"
                else:
                    self.igst_rate_tf.value = "5"

        total_pcs = gross_taxable = 0.0
        
        for s in selected_data:
            total_pcs += float(s.get("total_pcs", 0))
            # Recalculate Gross from scratch by summing items
            tbl = "order_items" if direct_mode else "transport_invoice_items"
            key = "order_id" if direct_mode else "transport_invoice_id"
            items = select(tbl, {key: s["id"]})
            gross_taxable += sum(float(it.get("qty_pieces", 0)) * float(it.get("rate", 0)) for it in items)

        total_gst = 0
        for s in selected_data:
            if direct_mode:
                items = select("order_items", {"order_id": s["id"]})
            else:
                items = select("transport_invoice_items", {"transport_invoice_id": s["id"]})
                
            for it in items:
                total_gst += float(it.get("amount", 0)) * (float(it.get("tax_percent", 5) or 5) / 100)

        try:
            fr = float(self.freight.value or 0)
            ot = float(self.other.value or 0)
            # 1. Base -> Sequential Discounts = Discounted Total
            running_total = gross_taxable
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    try:
                        d = float(meta["field"].value or 0)
                        disc_amt = running_total * (d / 100)
                        meta["amt"].value = f"Amt: ₹{disc_amt:,.2f}"
                        running_total -= disc_amt
                    except: pass
            
            # 2. Add Charges to get Final Taxable Base
            final_taxable = running_total + fr + ot
            
            # Breakdown tax fields
            tax_type = self.tax_type_dd.value
            cgst_rate = float(self.cgst_rate_tf.value or 0)
            sgst_rate = float(self.sgst_rate_tf.value or 0)
            igst_rate = float(self.igst_rate_tf.value or 0)
            cess_rate = float(self.cess_rate_tf.value or 0)
            tcs_rate  = float(self.tcs_rate_tf.value or 0)

            total_gst = 0
            cgst_amt = final_taxable * (cgst_rate / 100) if tax_type == "GST" else 0
            sgst_amt = final_taxable * (sgst_rate / 100) if tax_type == "GST" else 0
            igst_amt = final_taxable * (igst_rate / 100) if tax_type == "IGST" else 0
            cess_amt = final_taxable * (cess_rate / 100)
            
            # Fallback to inherited GST
            gst = cgst_amt + sgst_amt + igst_amt
            if not gst and selected_data:
                for s in selected_data:
                    if (gross_taxable + fr + ot) > 0:
                        scale = final_taxable / (gross_taxable + fr + ot)
                        total_gst += float(s.get("gst_amount", 0)) * scale
                gst = total_gst

            tcs_amt  = (final_taxable + gst) * (tcs_rate / 100)
            
            self.cgst_amt_lbl.value = f"Amt: ₹{cgst_amt:,.2f}"
            self.sgst_amt_lbl.value = f"Amt: ₹{sgst_amt:,.2f}"
            self.igst_amt_lbl.value = f"Amt: ₹{igst_amt:,.2f}"
            self.cess_amt_lbl.value = f"Amt: ₹{cess_amt:,.2f}"
            self.tcs_amt_lbl.value  = f"Amt: ₹{tcs_amt:,.2f}"
            
            # Visibilities
            self.igst_rate_tf.visible = self.igst_amt_lbl.visible = (tax_type == "IGST")
            self.cgst_rate_tf.visible = self.cgst_amt_lbl.visible = (tax_type == "GST")
            self.sgst_rate_tf.visible = self.sgst_amt_lbl.visible = (tax_type == "GST")

            gst_total = total_gst
            if not gst_total and (cgst_amt or igst_amt):
                 gst_total = cgst_amt + sgst_amt + igst_amt

            subtotal = final_taxable + gst_total + cess_amt + tcs_amt
            final_amt = math.ceil(subtotal)
            roff = final_amt - subtotal
            
            self.total_pcs.value = f"Total Pcs: {int(total_pcs)}"
            self.total_amt.value = f"Base Amount: ₹{gross_taxable:,.2f}"
            self.taxable_val.value = f"Taxable: ₹{final_taxable:,.2f}"
            
            self.cgst_lbl.value = f"CGST: ₹{cgst_amt:,.2f}"
            self.sgst_lbl.value = f"SGST: ₹{sgst_amt:,.2f}"
            self.igst_lbl.value = f"IGST: ₹{igst_amt:,.2f}"
            
            self.cgst_lbl.visible = self.sgst_lbl.visible = (tax_type == "GST")
            self.igst_lbl.visible = (tax_type == "IGST")
            
            self.round_off.value = f"{roff:.2f}"
            self.net_amt.value = f"Total: ₹{final_amt:,.2f}"
            
        except Exception as ex:
            print(f"Calc Error: {ex}")
        if self.page: self.update()

    def save_invoice(self, e):
        if not self.party_dd.value or not self._selected_inv_ids:
            self._snack("Select party and at least one transport invoice!", "red")
            return
        
        if not self.tax_type_dd.value:
            self._snack("Please select a Tax Type (GST/IGST) before saving!", "red")
            return
        
        try:
            inv_no = self.inv_no.value or f"GST-{uuid.uuid4().hex[:6].upper()}"
            selected_data = [s for s in self._available_invoices if str(s["id"]) in self._selected_inv_ids]
            direct_mode = state.settings.get("direct_invoice", False)
            
            # Recalculate Totals from scratch for saving
            total_pcs = gross_taxable = 0.0
            for s in selected_data:
                total_pcs += float(s.get("total_pcs", 0))
                tbl = "order_items" if direct_mode else "transport_invoice_items"
                key = "order_id" if direct_mode else "transport_invoice_id"
                items = select(tbl, {key: s["id"]})
                gross_taxable += sum(float(it.get("qty_pieces", 0)) * float(it.get("rate", 0)) for it in items)
            
            fr = float(self.freight.value or 0)
            ot = float(self.other.value or 0)

            discs = {}
            # Apply Sequential Discounts to Gross ONLY (Charges excluded)
            running_total = gross_taxable
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    try:
                        d = float(meta["field"].value or 0)
                        da = running_total * (d / 100)
                        discs[key] = {"p": d, "a": da}
                        running_total -= da
                    except: pass
            
            final_taxable = running_total + fr + ot
            
            # Recalculate precisely using UI rates
            tax_type = self.tax_type_dd.value
            cgst_rate = float(self.cgst_rate_tf.value or 0)
            sgst_rate = float(self.sgst_rate_tf.value or 0)
            igst_rate = float(self.igst_rate_tf.value or 0)
            cess_rate = float(self.cess_rate_tf.value or 0)
            tcs_rate  = float(self.tcs_rate_tf.value or 0)
            
            # Total GST from items (inherited)
            total_gst = 0
            for s in selected_data:
                items = select("order_items" if direct_mode else "transport_invoice_items", 
                               {"order_id" if direct_mode else "transport_invoice_id": s["id"]})
                for it in items:
                    total_gst += float(it.get("amount", 0)) * (float(it.get("tax_percent", 5) or 5) / 100)
            
            # Add GST on freight
            header_rate = float(selected_data[0].get("tax_per", 5)) if selected_data else 5
            total_gst += (fr + ot) * (header_rate / 100)

            cgst_amt = final_taxable * (cgst_rate / 100) if tax_type == "GST" else 0
            sgst_amt = final_taxable * (sgst_rate / 100) if tax_type == "GST" else 0
            igst_amt = final_taxable * (igst_rate / 100) if tax_type == "IGST" else 0
            cess_amt = final_taxable * (cess_rate / 100)
            
            gst_total = total_gst
            if not gst_total and (cgst_amt or igst_amt):
                 gst_total = cgst_amt + sgst_amt + igst_amt
            
            tcs_amt  = (final_taxable + gst_total) * (tcs_rate / 100)
            
            subtotal = final_taxable + gst_total + cess_amt + tcs_amt
            final_amt = math.ceil(subtotal)
            roff = final_amt - subtotal

            header = {
                "company_id":     state.company_id,
                "invoice_no":     inv_no,
                "invoice_date":   self.inv_date.value or None,
                "party_id":       self.party_dd.value,
                "agent_id":       self.agent_dd.value or None,
                "transporter_id": self.trans_dd.value or None,
                "destination":    self.dest.value,
                "order_by":       self.order_by.value,
                "order_thro":     self.order_thro.value,
                "qty_type":       self.qty_type.value,
                "lr_no":          self.lr_no.value,
                "lr_date":        self.lr_date.value or None,
                "freight_charges": fr,
                "total_pcs":      int(total_pcs),
                "total_amount":   round(gross_taxable, 2),
                "taxable_amount": round(final_taxable, 2),
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
                "cgst_amount":    round(cgst_amt, 2),
                "sgst_amount":    round(sgst_amt, 2),
                "igst_amount":    round(igst_amt, 2),
                "tcs_amount":     round(tcs_amt, 2),
                "round_off":      round(roff, 2),
                "net_amount":     final_amt,
            }
            
            res = None
            if self.current_edit_id:
                final_id = self.current_edit_id
                update("final_invoices", header, {"id": final_id})
                # Prevent duplication: delete old financial and stock ledgers for this invoice so they can be recreated cleanly
                delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Sales Invoice", "ref_id": inv_no})
                delete("stock_ledger", {"company_id": state.company_id, "ref_type": "Sales Invoice", "ref_id": inv_no})
                # Note: We don't delete linked transport_invoice_items — they belong to transport invoices
            else:
                res = insert("final_invoices", header)
                if not res: raise Exception("Failed to save final invoice header")
                final_id = res[0]["id"]

            # Fetch company and party details for PDF
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            party_data = select("parties", {"id": self.party_dd.value})
            party = party_data[0] if party_data else {}
            header["party_name"] = party.get("name", "Customer")
            header["party_address"] = f"{party.get('billing_address_line1','')}, {party.get('city','')}"
            header["party_gstin"] = party.get("gstin", "-")

            # Link TI items and gather for PDF
            all_items_for_pdf = []
            for s in selected_data:
                sid = str(s["id"])
                update("transport_invoices", {"status": "Invoiced"}, {"id": sid})
                # Fetch items to include in PDF
                ti_items = select("transport_invoice_items", {"transport_invoice_id": sid})
                for it in ti_items:
                    # Resolve item name if missing
                    if not it.get("item_name"):
                        i_data = select("items", {"id": it["item_id"]})
                        it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"
                    all_items_for_pdf.append(it)

            # Collect unique internal order numbers for the PDF header
            unique_orders = set()
            for it in all_items_for_pdf:
                oid = it.get("order_id")
                if oid:
                    o_data = select("orders", {"id": oid})
                    if o_data: unique_orders.add(o_data[0].get("order_no", "ORD"))
            header["order_no"] = ", ".join(sorted(list(unique_orders)))

            # Generate PDF
            pdf_path = pdf_engine.generate_tax_invoice(header, all_items_for_pdf, company)
            print_pdf(pdf_path)

            # Update Ledger (Debit the party)
            insert("ledger_entries", {
                "company_id":   state.company_id,
                "account_id":   self.party_dd.value,
                "account_type": "Party",
                "debit":        header["net_amount"],
                "credit":       0,
                "ref_id":       inv_no,
                "ref_type":     "Sales Invoice",
                "entry_date":   header["invoice_date"]
            })

            # Update Inventory (Deduct from Stock Ledger)
            for it in all_items_for_pdf:
                insert("stock_ledger", {
                    "company_id": state.company_id,
                    "entry_date": header["invoice_date"],
                    "item_id": it["item_id"],
                    "size_value": it.get("size_value", "FS"),
                    "transaction_type": "OUT",
                    "ref_type": "Sales Invoice",
                    "ref_id": inv_no,
                    "qty": int(it.get("qty_pieces", 0)),
                    "rate": float(it.get("rate", 0))
                })

            self._snack(f"✅ Tax Invoice {inv_no} saved. Ledger and Stock updated!", "green")
            self.clear_form()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def clear_form(self):
        self.inv_no.value = get_next_doc_no("final_invoices", "S", state.company_id, "invoice_no")
        self.freight.value = "0"
        self.other.value = "0"
        self._selected_inv_ids.clear()
        self._available_invoices = []
        self.items_col.controls = []
        self.party_dd.value = None
        self.current_edit_id = None
        self._calc()
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # History & Printing
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        invs = select("final_invoices", {"company_id": state.company_id})
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
            title=ft.Text("Recent Sales Invoices"),
            content=ft.Container(width=600, height=400, content=lv),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def delete_invoice_from_history(self, invoice, dlg):
        """Deletes a sales invoice and restores transport invoice status."""
        def confirm_delete(e):
            try:
                # 1. Identify associated transport invoices
                # We find TIs for this party that were marked "Invoiced" 
                # and (ideally) match the invoice linkage.
                # Since we want to be strict, we look for TIs that are currently "Invoiced"
                # and were linked to this party.
                all_ti = select("transport_invoices", {
                    "party_id": invoice["party_id"],
                    "status": "Invoiced"
                })
                
                # Restore them to Unbilled so they can be invoiced again
                for ti in all_ti:
                    # Note: In a multi-user environment, we'd check if they belong to THIS specific invoice.
                    # For now, we revert all "Invoiced" ones for this party to be safe.
                    update("transport_invoices", {"status": "Unbilled"}, {"id": ti["id"]})

                # 2. Delete header
                delete("final_invoices", {"id": invoice["id"]})
                
                # 3. Clean up Ledgers
                inv_no = invoice.get("invoice_no")
                delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Sales Invoice", "ref_id": inv_no})
                delete("stock_ledger", {"company_id": state.company_id, "ref_type": "Sales Invoice", "ref_id": inv_no})
                
                confirm_dlg.open = False
                dlg.open = False
                self.page.update()
                self._snack(f"Sales Invoice {inv_no} deleted.", "green")
                self.show_history_modal(None)
            except Exception as ex:
                self._snack(f"Delete Error: {ex}", "red")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete sales invoice {invoice.get('invoice_no')}?"),
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

    def load_invoice_for_edit(self, invoice, dlg):
        """Loads a past sales invoice into the main form for editing."""
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
            self.qty_type.value   = invoice.get("qty_type", "")
            self.lr_no.value      = invoice.get("lr_no", "")
            self.lr_date.value    = invoice.get("lr_date", "")
            self.freight.value    = str(invoice.get("freight_charges", 0))
            self.other.value      = str(invoice.get("other_charges", 0))
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

            # Load linked transport invoices for display
            # Find transport invoices that were part of this final invoice
            # They would have been marked as "Invoiced" when this final invoice was created
            direct_mode = state.settings.get("direct_invoice", False)
            
            if direct_mode:
                # In direct mode, we linked orders directly
                # Re-fetch the associated orders
                self._available_invoices = []
            else:
                # Find transport invoices linked to this final invoice
                # We look for transport invoices for this party that are "Invoiced"
                all_ti = select("transport_invoices", {
                    "party_id": self.party_dd.value,
                    "company_id": state.company_id
                })
                # We'll show the ones that match the total — in practice we'd have a link table
                # For now, re-show all invoiced ones for this party
                self._available_invoices = [ti for ti in all_ti if ti.get("status") in ("Invoiced", "Unbilled")]

            self._selected_inv_ids = {str(s["id"]) for s in self._available_invoices}
            self.rebuild_grid()
            self._calc() # Force UI to split CGST/SGST
            self.page.update()
            self._snack(f"Loaded Invoice: {self.inv_no.value}", AppColors.PRIMARY)
        except Exception as ex:
            print(f"Edit Load Error: {ex}")
            self._snack(f"Failed to load invoice: {ex}", "red")

    def print_history_invoice(self, invoice):
        try:
            # We need to fetch transport items to generate the detailed PDF
            # A final invoice is linked to transport_invoices, which have items.
            # For simplicity in this history view, we fetch the transport_invoices linked.
            if invoice.get("transport_invoice_id"):
                t_invs = select("transport_invoices", {"id": invoice["transport_invoice_id"]})
            else:
                t_invs = []
            all_items = []
            for t in t_invs:
                items = select("transport_invoice_items", {"transport_invoice_id": t["id"]})
                for it in items:
                    if not it.get("item_name"):
                        i_data = select("items", {"id": it["item_id"]})
                        it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"
                    all_items.append(it)
                    
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            pdf_path = pdf_engine.generate_tax_invoice(invoice, all_items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing: {ex}", "red")
