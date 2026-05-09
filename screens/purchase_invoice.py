import flet as ft
import uuid
import math
import os
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
from core.pdf_gen import pdf_engine, print_pdf

class PurchaseInvoiceTab(ft.Column):
    """
    Purchase Invoice (The final GST-compliant Tax Invoice)
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
        self.party_dd  = ft.Dropdown(label="Select Supplier *",  width=280, on_change=self.on_party_change, **S)
        
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
        self.total_pcs   = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        self.total_amt   = ft.Text("Base Amount: ₹0.00", size=14, weight="bold")
        
        # Tax Breakup
        self.taxable_val = ft.Text("Taxable Value: ₹0.00", size=16, weight="bold")
        self.cgst_lbl    = ft.Text("CGST (2.5%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.sgst_lbl    = ft.Text("SGST (2.5%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.igst_lbl    = ft.Text("IGST (5.0%): ₹0.00", size=13, color=AppColors.TEXT_SUB)
        self.round_off   = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self._calc, **S)
        self.net_amt     = ft.Text("Invoice Total: ₹0.00", size=24, weight="bold", color=AppColors.PRIMARY)

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
                        ft.Text("Purchase Tax Invoice", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15, wrap=True),
                    ft.Row([self.inv_no, self.inv_date], spacing=10, wrap=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                
                # Row 2: Supplier and Logistic Info
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
                ft.Checkbox(on_change=self.toggle_all),
                ft.Text("TRANS INV NO", width=140, size=11, weight="bold"),
                ft.Text("LR NO",       width=100, size=11, weight="bold"),
                ft.Text("LR DATE",     width=100, size=11, weight="bold"),
                ft.Text("CASES",      width=60,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("PCS",        width=80,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("TAXABLE",    expand=True, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
            ]),
        )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Column([
                # Row 1: Summary
                ft.Row([
                    ft.Column([
                        self.total_pcs, self.total_amt,
                    ], spacing=4),
                    ft.Container(expand=True),
                    ft.Column([
                        self.cgst_lbl, self.sgst_lbl, self.igst_lbl
                    ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                # Row 2: Final Totals and Actions
                ft.Row([
                    self.taxable_val,
                    ft.Container(expand=True),
                    ft.Row([
                        self.round_off,
                        ft.Container(width=10),
                        self.net_amt,
                        ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.did_mount(), tooltip="Refresh Data"),
                        ft.ElevatedButton(
                            "Confirm & Save Invoice",
                            icon=ft.icons.CHECK_CIRCLE,
                            on_click=self.save_invoice,
                            height=50,
                            style=AppStyles.primary_button_style(),
                        ),
                    ], spacing=10, wrap=True)
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
            ], spacing=15),
        )

    def did_mount(self):
        self.load_dropdowns()
        if not self.inv_no.value:
            self.inv_no.value = get_next_doc_no("purchase_invoices", "S", state.company_id, "invoice_no")

    def load_dropdowns(self):
        if not state.company_id: return
        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Supplier", "Both"]})
        agents       = select("agents",       {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        
        self.party_dd.options = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.agent_dd.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.trans_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        
        if not self.inv_no.value:
            self.inv_no.value = get_next_doc_no("purchase_invoices", "S", state.company_id, "invoice_no")
            
        if self.page: self.update()

    def on_party_change(self, e):
        supplier_id = self.party_dd.value
        if not supplier_id: return
        pdata = select("parties", {"id": supplier_id})
        if pdata:
            p = pdata[0]
            self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type = p.get("tax_type", "IGST") or "IGST"
        
        self.load_invoices(supplier_id)

    def load_invoices(self, supplier_id):
        direct_mode = state.settings.get("direct_invoice", False)
        
        if direct_mode:
            # Pull orders that aren't fully invoiced yet
            # In a real app, you'd track 'invoiced_status'. For now, pull Pending/Partial.
            self._available_invoices = select("orders", {
                "supplier_id": supplier_id, 
                "company_id": state.company_id
            })
            # Filter for non-completed in Python for simplicity
            self._available_invoices = [o for o in self._available_invoices if o.get("status") != "Completed"]
        else:
            self._available_invoices = select("purchase_orders", {
                "supplier_id": supplier_id, 
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
        if val: self._selected_inv_ids.add(inv_id)
        else: self._selected_inv_ids.discard(inv_id)
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
        total_pcs = gross_taxable = 0.0
        selected_data = [s for s in self._available_invoices if str(s["id"]) in self._selected_inv_ids]
        direct_mode = state.settings.get("direct_invoice", False)
        
        for s in selected_data:
            total_pcs += float(s.get("total_pcs", 0))
            if direct_mode:
                gross_taxable += float(s.get("total_amount", 0))
            else:
                net = float(s.get("net_amount", 0))
                rate = float(s.get("tax_per", 5))
                gross_taxable += net / (1 + rate/100)

        try:
            fr = float(self.freight.value or 0)
            ot = float(self.other.value or 0)
            final_taxable = gross_taxable + fr + ot
            
            subtotal = final_taxable + gst_total
            final_amt = math.ceil(subtotal)
            roff = final_amt - subtotal
            
            self.total_pcs.value = f"Total Pcs: {int(total_pcs)}"
            self.total_amt.value = f"Base Amount: ₹{gross_taxable:,.2f}"
            self.taxable_val.value = f"Taxable Value: ₹{final_taxable:,.2f}"
            
            if self._party_tax_type == "IGST":
                self.igst_lbl.value = f"IGST ({rate:.1f}%): ₹{gst_total:,.2f}"
                self.cgst_lbl.visible = self.sgst_lbl.visible = False
                self.igst_lbl.visible = True
            else:
                self.cgst_lbl.value = f"CGST ({rate/2:.2f}%): ₹{gst_total/2:,.2f}"
                self.sgst_lbl.value = f"SGST ({rate/2:.2f}%): ₹{gst_total/2:,.2f}"
                self.igst_lbl.visible = False
                self.cgst_lbl.visible = self.sgst_lbl.visible = True
                
            self.round_off.value = f"{roff:.2f}"
            self.net_amt.value = f"Invoice Total: ₹{final_amt:,.2f}"
        except Exception: pass
        if self.page: self.update()

    def save_invoice(self, e):
        if not self.party_dd.value or not self._selected_inv_ids:
            self._snack("Select party and at least one transport invoice!", "red")
            return
        
        try:
            inv_no = self.inv_no.value or f"GST-{uuid.uuid4().hex[:6].upper()}"
            selected_data = [s for s in self._available_invoices if str(s["id"]) in self._selected_inv_ids]
            
            total_pcs = sum(float(s.get("total_pcs", 0)) for s in selected_data)
            gross_taxable = sum(float(s.get("net_amount", 0)) / (1 + float(s.get("tax_per", 5))/100) for s in selected_data)
            
            fr = float(self.freight.value or 0)
            ot = float(self.other.value or 0)
            final_taxable = gross_taxable + fr + ot
            rate = self._party_gst_rate
            gst_total = final_taxable * (rate / 100)
            
            subtotal = final_taxable + gst_total
            final_amt = math.ceil(subtotal)
            roff = final_amt - subtotal

            header = {
                "company_id":     state.company_id,
                "invoice_no":     inv_no,
                "invoice_date":   self.inv_date.value or None,
                "supplier_id":       self.party_dd.value,
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
                "tax_type":       self._party_tax_type,
                "tax_per":        rate,
                "cgst_amount":    round(gst_total/2, 2) if self._party_tax_type != "IGST" else 0,
                "sgst_amount":    round(gst_total/2, 2) if self._party_tax_type != "IGST" else 0,
                "igst_amount":    round(gst_total, 2) if self._party_tax_type == "IGST" else 0,
                "round_off":      round(roff, 2),
                "net_amount":     final_amt,
            }
            
            res = None
            if self.current_edit_id:
                final_id = self.current_edit_id
                update("purchase_invoices", header, {"id": final_id})
                # Prevent duplication: delete old financial and stock ledgers for this invoice so they can be recreated cleanly
                delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Purchase Invoice", "ref_id": inv_no})
                delete("stock_ledger", {"company_id": state.company_id, "ref_type": "Purchase Invoice", "ref_id": inv_no})
                # Note: We don't delete linked purchase_order_items — they belong to transport invoices
            else:
                res = insert("purchase_invoices", header)
                if not res: raise Exception("Failed to save final invoice header")
                final_id = res[0]["id"]

            # Fetch company and party details for PDF
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            party_data = select("parties", {"id": self.party_dd.value})
            party = party_data[0] if party_data else {}
            header["party_name"] = party.get("name", "Supplier")
            header["party_address"] = f"{party.get('billing_address_line1','')}, {party.get('city','')}"
            header["party_gstin"] = party.get("gstin", "-")

            # Link TI items and gather for PDF
            all_items_for_pdf = []
            for s in selected_data:
                sid = str(s["id"])
                update("purchase_orders", {"status": "Invoiced"}, {"id": sid})
                # Fetch items to include in PDF
                ti_items = select("purchase_order_items", {"purchase_order_id": sid})
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

            # Update Ledger (Credit the party)
            insert("ledger_entries", {
                "company_id":   state.company_id,
                "account_id":   self.party_dd.value,
                "account_type": "Party",
                "credit":        header["net_amount"],
                "debit":       0,
                "ref_id":       inv_no,
                "ref_type":     "Purchase Invoice",
                "entry_date":   header["invoice_date"]
            })

            # Update Inventory (Deduct from Stock Ledger)
            for it in all_items_for_pdf:
                insert("stock_ledger", {
                    "company_id": state.company_id,
                    "entry_date": header["invoice_date"],
                    "item_id": it["item_id"],
                    "size_value": it.get("size_value", "FS"),
                    "transaction_type": "IN",
                    "ref_type": "Purchase Invoice",
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
        self.inv_no.value = get_next_doc_no("purchase_invoices", "S", state.company_id, "invoice_no")
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
        invs = select("purchase_invoices", {"company_id": state.company_id})
        invs.sort(key=lambda x: x.get("invoice_date", ""), reverse=True)
        
        parties = select("parties", {"company_id": state.company_id})
        party_map = {str(p["id"]): p["name"] for p in parties}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for inv in invs:
            p_name = party_map.get(str(inv.get("supplier_id")), "Unknown")
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
                            ft.IconButton(ft.icons.EDIT_INLINED, tooltip="Edit Invoice", icon_color=AppColors.PRIMARY,
                                          on_click=lambda e, i=inv: self.load_invoice_for_edit(i, dlg)),
                            ft.IconButton(ft.icons.PRINT, tooltip="Print Invoice", icon_color=ft.colors.BLUE_700, 
                                          on_click=lambda e, i=inv: self.print_history_invoice(i)),
                            ft.IconButton(ft.icons.DELETE_INLINE, tooltip="Delete Invoice", icon_color="red",
                                          on_click=lambda e, i=inv: self.delete_invoice_from_history(i, dlg))
                        ])
                    ])
                )
            )
            
        dlg = ft.AlertDialog(
            title=ft.Text("Recent Purchase Invoices"),
            content=ft.Container(width=600, height=400, content=lv),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def delete_invoice_from_history(self, invoice, dlg):
        """Deletes a purchase invoice and restores transport invoice status."""
        def confirm_delete(e):
            try:
                # 1. Identify associated transport invoices
                # We need to find TIs for this party that are marked "Invoiced"
                # Since there's no direct link table, we look for TIs that match the net/tax
                # But safer is to find TIs linked to this party with status "Invoiced"
                all_ti = select("purchase_orders", {
                    "supplier_id": invoice["supplier_id"],
                    "status": "Invoiced"
                })
                
                # Restore them to Unbilled
                for ti in all_ti:
                    update("purchase_orders", {"status": "Unbilled"}, {"id": ti["id"]})

                # 2. Delete header
                delete("purchase_invoices", {"id": invoice["id"]})
                
                # 3. Clean up Ledgers
                inv_no = invoice.get("invoice_no")
                delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Purchase Invoice", "ref_id": inv_no})
                delete("stock_ledger", {"company_id": state.company_id, "ref_type": "Purchase Invoice", "ref_id": inv_no})
                
                confirm_dlg.open = False
                dlg.open = False
                self.page.update()
                self._snack(f"Purchase Invoice {invoice.get('invoice_no')} deleted.", "green")
                self.show_history_modal(None)
            except Exception as ex:
                self._snack(f"Delete Error: {ex}", "red")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete purchase invoice {invoice.get('invoice_no')}?"),
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
        """Loads a past purchase invoice into the main form for editing."""
        try:
            self._close_dialog(dlg)
            self.clear_form()
            
            self.current_edit_id  = invoice["id"]
            self.inv_no.value     = invoice.get("invoice_no", "")
            self.inv_date.value   = invoice.get("invoice_date", "")
            self.party_dd.value   = str(invoice.get("supplier_id")) if invoice.get("supplier_id") else None
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
                all_ti = select("purchase_orders", {
                    "supplier_id": self.party_dd.value,
                    "company_id": state.company_id
                })
                # We'll show the ones that match the total — in practice we'd have a link table
                # For now, re-show all invoiced ones for this party
                self._available_invoices = [ti for ti in all_ti if ti.get("status") in ("Invoiced", "Unbilled")]

            self._selected_inv_ids = {str(s["id"]) for s in self._available_invoices}
            self.rebuild_grid()

            self._snack(f"Loaded Invoice: {self.inv_no.value}", AppColors.PRIMARY)
        except Exception as ex:
            print(f"Edit Load Error: {ex}")
            self._snack(f"Failed to load invoice: {ex}", "red")

    def print_history_invoice(self, invoice):
        try:
            # We need to fetch transport items to generate the detailed PDF
            # A final invoice is linked to purchase_orders, which have items.
            # For simplicity in this history view, we fetch the purchase_orders linked.
            t_invs = select("purchase_orders", {"purchase_invoice_id": invoice["id"]})
            all_items = []
            for t in t_invs:
                items = select("purchase_order_items", {"purchase_order_id": t["id"]})
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
