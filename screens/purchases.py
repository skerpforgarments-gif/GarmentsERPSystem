import flet as ft
import uuid
import math
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
from components.size_matrix import SizeMatrixModal, sort_sizes
from core.pdf_gen import pdf_engine, print_pdf
import os


class PurchaseOrderTab(ft.Column):
    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        # --- Data ---
        self.order_items        = []
        self.all_items_metadata = {}
        self.matrix_modal       = None
        self.current_edit_id    = None

        # ── Header controls ───────────────────────────────────
        S = AppStyles.get_input_style()
        self.po_no      = ft.TextField(label="PO No", width=150, **S)
        self.po_date    = ft.TextField(label="Date", width=140, value=date.today().isoformat(), **S)
        self.supplier_dd = ft.Dropdown(label="Select Supplier *", width=300, on_change=self.on_supplier_change, **S)
        self.agent_dd    = ft.Dropdown(label="Agent", width=180, **S)
        self.transporter_dd = ft.Dropdown(label="Transporter", width=220, **S)
        self.price_list_dd  = ft.Dropdown(label="Price List", width=180, **S)
        self.price_type_dd  = ft.Dropdown(
            label="Type", width=120, value="Wholesale",
            options=[ft.dropdown.Option(k) for k in ("Wholesale", "Retail", "MRP")],
            **S
        )
        self.destination = ft.TextField(label="Destination", width=160, **S)
        self.remarks     = ft.TextField(label="Remarks",     width=250, **S)
        self.freight_charge = ft.TextField(label="Freight", value="0", width=100, on_change=self.on_calc_change, **S)
        self.other_charge   = ft.TextField(label="Other Charges", value="0", width=120, on_change=self.on_calc_change, **S)

        # ── Footer controls ───────────────────────────────────
        self.no_of_items_lbl = ft.Text("No. Of Items: 0", size=13, weight="w500")
        self.total_pcs    = ft.Text("Total Pcs: 0",    size=13, weight="bold")

        self.trade_disc   = ft.TextField(label="Trade %",  value="0", width=80, on_change=self.on_calc_change, **S)
        self.td_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)

        self.taxable_value = ft.Text("Taxable: ₹0.00",   size=14, weight="bold")

        self.tax_type_dd = ft.Dropdown(
            label="Tax Type",
            options=[ft.dropdown.Option("GST"), ft.dropdown.Option("IGST")],
            value="GST", width=120, on_change=self.on_calc_change
        )
        self.gst_rate_tf  = ft.TextField(label="GST %",  value="5",   width=60, on_change=self.on_calc_change, **S)
        self.cgst_rate_tf = ft.TextField(label="CGST %", value="2.5", width=60, on_change=self.on_calc_change, **S)
        self.cgst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        self.sgst_rate_tf = ft.TextField(label="SGST %", value="2.5", width=60, on_change=self.on_calc_change, **S)
        self.sgst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        self.igst_rate_tf = ft.TextField(label="IGST %", value="5",   width=60, on_change=self.on_calc_change, visible=False, **S)
        self.igst_amt_lbl = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB, visible=False)
        self.round_off    = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self.on_calc_change, **S)
        self.gross_amount = ft.Text("Total: ₹0.00", size=20, weight="bold", color=AppColors.PRIMARY)

        # ── Scrollable items area ─────────────────────────────
        self.items_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)
        self.items_area = ft.Container(
            expand=True, bgcolor=ft.colors.WHITE,
            border=ft.border.all(1, "#E2E8F0"), border_radius=8,
            padding=0, content=self.items_col,
        )

        self.controls = [
            self._build_header(),
            self._build_col_header(),
            self.items_area,
            ft.Divider(height=1, color="#E2E8F0"),
            self._build_footer(),
        ]

    # ─────────────────────────────────────────────────────────
    # Static UI builders
    # ─────────────────────────────────────────────────────────
    def _build_header(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Text("Purchase Order Entry", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15, wrap=True),
                    ft.Row([self.po_no, self.po_date], spacing=10, wrap=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                ft.Row([
                    self.supplier_dd, self.agent_dd, self.transporter_dd, self.destination,
                ], spacing=12, wrap=True),
                ft.Row([
                    self.price_list_dd, self.price_type_dd, self.remarks,
                    ft.VerticalDivider(width=20),
                    self.freight_charge, self.other_charge,
                ], spacing=12, wrap=True),
                ft.Row([
                    ft.ElevatedButton("Add Item", icon=ft.icons.ADD,
                                      on_click=self.open_size_matrix,
                                      style=AppStyles.primary_button_style()),
                    ft.TextButton("Clear All", icon=ft.icons.DELETE_SWEEP,
                                  on_click=self.clear_form),
                ]),
            ], spacing=15),
        )

    def _build_col_header(self):
        return ft.Container(
            bgcolor="#F1F5F9",
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Row([
                ft.Text("ITEM NAME",  width=250, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("SIZE",       width=100, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("QTY",        width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("RATE",       width=100, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("AMOUNT",     expand=True, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("ACT",        width=60,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.CENTER),
            ], spacing=0)
        )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Column([
                ft.Row([
                    ft.Column([self.no_of_items_lbl, self.total_pcs], spacing=5),
                    ft.Container(expand=True),
                    ft.Column([self.trade_disc, self.td_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                ft.Row([
                    ft.Column([
                        self.taxable_value,
                        ft.Row([
                            self.tax_type_dd, self.gst_rate_tf,
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.cgst_rate_tf, self.cgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([self.sgst_rate_tf, self.sgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([self.igst_rate_tf, self.igst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ], spacing=2, expand=True),
                    ft.VerticalDivider(width=1, color="#E2E8F0"),
                    ft.Column([self.round_off], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(width=20),
                    ft.Column([
                        ft.Text("Grand Total", size=11, color=AppColors.TEXT_SUB, weight="w500"),
                        self.gross_amount,
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                    ft.Container(width=10),
                    ft.ElevatedButton(
                        "Confirm & Save",
                        icon=ft.icons.SAVE_ALT,
                        on_click=self.save_po,
                        height=48,
                        style=AppStyles.primary_button_style(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            ], spacing=10),
        )

    # ─────────────────────────────────────────────────────────
    # Lifecycle & Loaders
    # ─────────────────────────────────────────────────────────
    def did_mount(self):
        if not state.company_id:
            return
        if not self.po_no.value:
            self.po_no.value = get_next_doc_no("purchase_orders", "PO", state.company_id, "po_no")
        self.load_dropdowns()
        if not self.order_items:
            self.add_item_row(None)

    def load_dropdowns(self):
        parties = select("parties", {"company_id": state.company_id, "party_type": ["Supplier", "Both"]})
        trans   = select("transporters", {"company_id": state.company_id})
        
        self.supplier_dd.options = [ft.dropdown.Option(str(p["id"]), p["name"]) for p in parties]
        self.transporter_dd.options = [ft.dropdown.Option(str(t["id"]), t["name"]) for t in trans]
        
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # Lifecycle & Loaders
    # ─────────────────────────────────────────────────────────
    def did_mount(self):
        if not state.company_id:
            return
        self.load_metadata()
        if not self.po_no.value:
            self.po_no.value = get_next_doc_no("purchase_orders", "PO", state.company_id, "po_no")

    def load_metadata(self):
        if not state.company_id:
            return
        items = select("items", {"company_id": state.company_id, "item_type": ["Supplies", "Both"]})
        self.all_items_metadata = {str(i["id"]): i for i in items}

        self.matrix_modal = SizeMatrixModal(on_submit=self.add_matrix_results)
        if self.page and self.matrix_modal not in self.page.overlay:
            self.page.overlay.append(self.matrix_modal)
            self.page.update()
        self.matrix_modal.load_items(items)

        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Supplier", "Both"]})
        agents       = select("agents",       {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        price_lists  = select("price_lists",  {"company_id": state.company_id})

        self.supplier_dd.options    = [ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in parties]
        self.agent_dd.options       = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.transporter_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        self.price_list_dd.options  = [ft.dropdown.Option(key=str(p["id"]), text=p["list_name"]) for p in price_lists]

        if self.page: self.update()

    def on_supplier_change(self, e):
        party_id = self.supplier_dd.value
        if not party_id: return
        data = select("parties", {"id": party_id})
        if data:
            p = data[0]
            if p.get("transporter_id"): self.transporter_dd.value = str(p["transporter_id"])
            if p.get("agent_id"):       self.agent_dd.value       = str(p["agent_id"])
            if p.get("price_list_id"):  self.price_list_dd.value  = str(p["price_list_id"])
            self.destination.value = p.get("delivery_city") or p.get("billing_city", "")
            self.trade_disc.value  = str(p.get("discount_trade", 0) or 0)
            self.gst_rate_tf.value = str(p.get("gst_percent", 5) or 5)
            self.tax_type_dd.value = str(p.get("tax_type", "GST") or "GST").upper()
            self.on_calc_change(None)
            if self.page: self.update()

    def open_size_matrix(self, e):
        if not self.price_list_dd.value:
            self._snack("Please select a Price List first!", "orange")
            return
        self.matrix_modal.reset()
        self.matrix_modal.price_list_id = self.price_list_dd.value
        self.matrix_modal.price_type    = self.price_type_dd.value or "Wholesale"
        self.matrix_modal.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────
    # Grid (Sales-style: one row per item/size/rate)
    # ─────────────────────────────────────────────────────────
    def add_matrix_results(self, results):
        """Receives results from SizeMatrixModal, groups by rate."""
        groups = {}
        for res in results:
            key = (res["item_id"], res["rate"])
            if key not in groups:
                groups[key] = {"item_name": res["item_name"], "sizes": [], "qty": 0}
            groups[key]["sizes"].append(res["size"])
            groups[key]["qty"] += res["qty"]

        for (item_id, rate), data in groups.items():
            self.order_items.append({
                "item_id":     item_id,
                "item_name":   data["item_name"],
                "sizes_label": ", ".join(sort_sizes(data["sizes"])),
                "rate":        rate,
                "qty":         data["qty"],
            })
        self.rebuild_grid()

    def _make_row(self, item):
        """Build a single editable item row (matching Sales style)."""
        amt_lbl = ft.Text("", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY)

        def update_labels():
            pcs = item["qty"]
            amount = pcs * item["rate"]
            amt_lbl.value = f"₹{amount:,.2f}"
            item["amount"] = amount
            if amt_lbl.page:
                amt_lbl.update()

        def update_field(f, v):
            try:
                if f == "qty":  item["qty"]  = int(v or 0)
                elif f == "rate": item["rate"] = float(v or 0)
                update_labels()
                self.on_calc_change(None)
            except ValueError: pass

        update_labels()

        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                ft.Text(item["item_name"],   width=250, size=13, weight="w500"),
                ft.Text(item["sizes_label"], width=100, size=11, color=AppColors.PRIMARY, italic=True),
                ft.Container(width=80, content=ft.TextField(
                    value=str(item["qty"]), text_align=ft.TextAlign.RIGHT,
                    on_change=lambda e: update_field("qty", e.control.value),
                    **{**AppStyles.get_input_style(), "height": 35}
                )),
                ft.Container(width=100, content=ft.TextField(
                    value=str(item["rate"]), text_align=ft.TextAlign.RIGHT,
                    on_change=lambda e: update_field("rate", e.control.value),
                    **{**AppStyles.get_input_style(), "height": 35}
                )),
                amt_lbl,
                ft.Container(width=60, content=ft.IconButton(
                    ft.icons.DELETE_OUTLINE, icon_color="red400", icon_size=18,
                    on_click=lambda _: self.remove_item(item)
                ), alignment=ft.alignment.center),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def remove_item(self, item):
        self.order_items.remove(item)
        self.rebuild_grid()

    def rebuild_grid(self):
        self.items_col.controls = [self._make_row(item) for item in self.order_items]
        self.on_calc_change(None)
        if self.page:
            self.items_col.update()

    # ─────────────────────────────────────────────────────────
    # Calculations
    # ─────────────────────────────────────────────────────────
    def on_calc_change(self, e=None):
        trigger = e.control if e and hasattr(e, "control") else None

        # Sync CGST/SGST if GST rate changed or mode switched
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

        total_pcs = 0
        gross_sum = 0

        for it in self.order_items:
            try:
                pcs = it.get("qty", 0)
                amt = it.get("amount", pcs * it.get("rate", 0))
                total_pcs += pcs
                gross_sum += amt
            except: pass

        # Apply Discount
        td_p = float(self.trade_disc.value or 0)
        td_amt = gross_sum * (td_p / 100)
        self.td_amt_lbl.value = f"Amt: ₹{td_amt:,.2f}"

        taxable = gross_sum - td_amt
        tax_type = str(self.tax_type_dd.value or "GST").upper()

        c_rate = float(self.cgst_rate_tf.value or 0)
        s_rate = float(self.sgst_rate_tf.value or 0)
        i_rate = float(self.igst_rate_tf.value or 0)

        cgst_amt = taxable * (c_rate / 100) if tax_type == "GST" else 0
        sgst_amt = taxable * (s_rate / 100) if tax_type == "GST" else 0
        igst_amt = taxable * (i_rate / 100) if tax_type == "IGST" else 0

        self.cgst_amt_lbl.value = f"Amt: ₹{cgst_amt:,.2f}"
        self.sgst_amt_lbl.value = f"Amt: ₹{sgst_amt:,.2f}"
        self.igst_amt_lbl.value = f"Amt: ₹{igst_amt:,.2f}"

        self.cgst_rate_tf.visible = self.cgst_amt_lbl.visible = (tax_type == "GST")
        self.sgst_rate_tf.visible = self.sgst_amt_lbl.visible = (tax_type == "GST")
        self.igst_rate_tf.visible = self.igst_amt_lbl.visible = (tax_type == "IGST")

        gst = cgst_amt + sgst_amt + igst_amt
        fr  = float(self.freight_charge.value or 0)
        oth = float(self.other_charge.value or 0)

        subtotal  = taxable + gst + fr + oth
        final_amt = math.ceil(subtotal)
        roff      = final_amt - subtotal

        self.no_of_items_lbl.value = f"No. Of Items: {len([i for i in self.order_items if i.get('item_id')])}"
        self.total_pcs.value       = f"Total Pcs: {int(total_pcs)}"
        self.taxable_value.value   = f"Taxable: ₹{taxable:,.2f}"
        self.round_off.value       = f"{roff:.2f}"
        self.gross_amount.value    = f"Total: ₹{final_amt:,.2f}"

        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # Save Logic
    # ─────────────────────────────────────────────────────────
    def save_po(self, e):
        if not state.company_id: return
        if not self.supplier_dd.value:
            self._snack("Please select a Supplier!", "red")
            return
        if not self.tax_type_dd.value:
            self._snack("Please select a Tax Type (GST/IGST)!", "red")
            return
        if not self.gst_rate_tf.value or float(self.gst_rate_tf.value or 0) <= 0:
            self._snack("Please enter a valid GST rate!", "red")
            return

        # Build items from the new data model
        valid_items = []
        for it in self.order_items:
            if not it.get("item_id"): continue
            sizes = [s.strip() for s in it.get("sizes_label", "FS").split(",")]
            qty_per_size = max(1, len(sizes))
            per_size_qty = it["qty"] // qty_per_size if qty_per_size else it["qty"]
            remainder = it["qty"] - (per_size_qty * qty_per_size)
            for i, sz in enumerate(sizes):
                q = per_size_qty + (1 if i < remainder else 0)
                if q > 0:
                    valid_items.append({
                        "item_id": it["item_id"],
                        "item_name": it.get("item_name", ""),
                        "size_value": sz,
                        "qty": q,
                        "rate": it["rate"]
                    })

        if not valid_items:
            self._snack("No items to save!", "red")
            return

        try:
            po_id = self.current_edit_id or str(uuid.uuid4())
            total_pcs = int(float(self.total_pcs.value.split(": ")[1]))
            taxable_str = self.taxable_value.value.replace("Taxable: ₹", "").replace(",", "")
            taxable_val = float(taxable_str)
            net_str = self.gross_amount.value.replace("Total: ₹", "").replace(",", "")
            net_val = float(net_str)

            header = {
                "company_id":     state.company_id,
                "po_no":          self.po_no.value,
                "po_date":        self.po_date.value,
                "supplier_id":    self.supplier_dd.value,
                "agent_id":       self.agent_dd.value or None,
                "transporter_id": self.transporter_dd.value or None,
                "destination":    self.destination.value,
                "remarks":        self.remarks.value,
                "freight":        float(self.freight_charge.value or 0),
                "other_charges":  float(self.other_charge.value or 0),
                "total_pcs":      total_pcs,
                "total_amount":   taxable_val,
                "tax_per":        float(self.gst_rate_tf.value or 0),
                "net_amount":     net_val,
                "status":         "Pending"
            }

            if self.current_edit_id:
                update("purchase_orders", header, {"id": po_id})
                delete("purchase_order_items", {"purchase_order_id": po_id})
            else:
                header["id"] = po_id
                insert("purchase_orders", header)

            for item in valid_items:
                insert("purchase_order_items", {
                    "purchase_order_id": po_id,
                    "company_id":      state.company_id,
                    "item_id":         item["item_id"],
                    "item_name":       item["item_name"],
                    "size_value":      item["size_value"],
                    "rate":            item["rate"],
                    "qty_pieces":      int(item["qty"]),
                    "amount":          item["qty"] * item["rate"],
                })

                insert("stock_ledger", {
                    "company_id":   state.company_id,
                    "entry_date":   header["po_date"],
                    "item_id":      item["item_id"],
                    "size_value":   item["size_value"],
                    "transaction_type": "IN",
                    "ref_type":     "Purchase Order",
                    "ref_id":       header["po_no"],
                    "qty":          int(item["qty"]),
                    "rate":         float(item["rate"])
                })

            insert("ledger_entries", {
                "company_id":   state.company_id,
                "account_id":   self.supplier_dd.value,
                "account_type": "Party",
                "debit":        0,
                "credit":       net_val,
                "ref_id":       header["po_no"],
                "ref_type":     "Purchase Order",
                "entry_date":   header["po_date"]
            })

            # ── Generate PDF ─────────────────────────────────
            saved = select("purchase_orders", {"id": po_id})
            if saved:
                po_data = saved[0]
                p_data = select("parties", {"id": po_data["supplier_id"]})
                if p_data:
                    po_data["party_name"] = p_data[0]["name"]
                if po_data.get("agent_id"):
                    a_data = select("agents", {"id": po_data["agent_id"]})
                    if a_data: po_data["agent_name"] = a_data[0]["name"]
                if po_data.get("transporter_id"):
                    t_data = select("transporters", {"id": po_data["transporter_id"]})
                    if t_data: po_data["transporter_name"] = t_data[0]["name"]

                # Alias fields for generate_order compatibility
                po_data["order_no"]   = po_data.get("po_no")
                po_data["order_date"] = po_data.get("po_date")
                po_data["net_amount"] = net_val

                po_items = select("purchase_order_items", {"purchase_order_id": po_id})
                comp = select("companies", {"id": state.company_id})
                company = comp[0] if comp else {}

                pdf_path = pdf_engine.generate_order(po_data, po_items, company)
                print_pdf(pdf_path)

            self._snack("✅ Purchase Order Saved & PDF Generated!", "green")
            self.clear_form()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    def clear_form(self, e=None):
        self.current_edit_id = None
        self.po_no.value = get_next_doc_no("purchase_orders", "PO", state.company_id, "po_no")
        self.supplier_dd.value = None
        self.agent_dd.value = None
        self.transporter_dd.value = None
        self.price_list_dd.value = None
        self.destination.value = ""
        self.remarks.value = ""
        self.freight_charge.value = "0"
        self.other_charge.value = "0"
        self.trade_disc.value = "0"
        self.order_items = []
        self.items_col.controls = []
        self.on_calc_change(None)
        if self.page: self.update()

    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def show_history_modal(self, e):
        orders = select("purchase_orders", {"company_id": state.company_id})
        orders.sort(key=lambda x: x.get("po_date", ""), reverse=True)
        parties = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for ord in orders:
            p_name = parties.get(str(ord.get("supplier_id")), "Unknown")
            lv.controls.append(
                ft.Container(
                    padding=10, bgcolor="white", border_radius=8, border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{ord.get('po_no')} | {ord.get('po_date')}", weight="bold"),
                            ft.Text(p_name, size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"₹ {float(ord.get('total_amount', 0)):,.2f}", weight="bold"),
                        ft.IconButton(ft.icons.EDIT, on_click=lambda e, o=ord: self.load_for_edit(o), icon_color=AppColors.PRIMARY),
                        ft.IconButton(ft.icons.PRINT, on_click=lambda e, o=ord: self.print_history_po(o)),
                        ft.IconButton(ft.icons.DELETE, on_click=lambda e, o=ord: self.delete_po_from_history(o), icon_color="red")
                    ])
                )
            )
        self._history_dlg = ft.AlertDialog(title=ft.Text("PO History"), content=ft.Container(lv, width=600, height=400))
        self.page.overlay.append(self._history_dlg); self._history_dlg.open = True; self.page.update()

    def load_for_edit(self, order):
        try:
            if hasattr(self, "_history_dlg"):
                self._history_dlg.open = False
            
            self.current_edit_id = order["id"]
            self.po_no.value = order["po_no"]
            self.po_date.value = order["po_date"]
            self.supplier_dd.value = str(order["supplier_id"])
            self.agent_dd.value = str(order.get("agent_id", "")) if order.get("agent_id") else None
            self.transporter_dd.value = str(order["transporter_id"]) if order.get("transporter_id") else None
            self.destination.value = order.get("destination", "")
            self.remarks.value = order.get("remarks", "")
            self.freight_charge.value = str(order.get("freight", 0))
            self.other_charge.value = str(order.get("other_charges", 0))

            # Load items and group by (item_id, rate)
            items = select("purchase_order_items", {"purchase_order_id": order["id"]})
            self.order_items = []
            self.items_col.controls = []

            grouped = {}
            for it in items:
                k = (str(it["item_id"]), float(it["rate"]))
                if k not in grouped:
                    # Resolve item name
                    i_data = select("items", {"id": it["item_id"]})
                    name = i_data[0]["item_name"] if i_data else "Unknown"
                    grouped[k] = {"item_name": name, "sizes": [], "qty": 0}
                grouped[k]["sizes"].append(it["size_value"])
                grouped[k]["qty"] += it["qty_pieces"]

            for (iid, rate), data in grouped.items():
                self.order_items.append({
                    "item_id":     iid,
                    "item_name":   data["item_name"],
                    "sizes_label": ", ".join(sort_sizes(data["sizes"])),
                    "rate":        rate,
                    "qty":         data["qty"],
                })

            self.rebuild_grid()
            self._snack(f"Loaded PO: {self.po_no.value}", AppColors.PRIMARY)
        except Exception as ex:
            self._snack(f"Edit Load Error: {ex}", "red")

    def print_history_po(self, order):
        items = select("purchase_order_items", {"purchase_order_id": order["id"]})
        for it in items:
            i_data = select("items", {"id": it["item_id"]})
            it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"
        comp = select("companies", {"id": state.company_id})
        pdf_path = pdf_engine.generate_order(order, items, comp[0] if comp else {})
        print_pdf(pdf_path)

    def delete_po_from_history(self, order):
        def confirm_delete(e):
            try:
                po_id = order["id"]
                po_no = order.get("po_no", "")

                # Check for dependencies (if any purchase invoices exist)
                linked = select("purchase_invoice_items", {"purchase_order_id": po_id})
                if linked:
                    self._snack("Cannot delete: This PO is linked to a Purchase Invoice.", "orange")
                    return

                # 1. Delete associated items
                delete("purchase_order_items", {"purchase_order_id": po_id})
                # 2. Delete the PO itself
                delete("purchase_orders", {"id": po_id})
                
                # 3. Clean up ledger & stock entries
                try:
                    delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Purchase Order", "ref_id": po_no})
                    delete("stock_ledger",  {"company_id": state.company_id, "ref_type": "Purchase Order", "ref_id": po_no})
                except Exception:
                    pass

                self._history_dlg.open = False
                self.page.update()
                self._snack(f"Purchase Order {po_no} deleted.", "green")
                self.show_history_modal(None)
            except Exception as ex:
                self._snack(f"Delete Error: {ex}", "red")

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Delete Purchase Order {order.get('po_no')}?"),
            actions=[
                ft.TextButton("Yes, Delete", on_click=confirm_delete, style=ft.ButtonStyle(color="red")),
                ft.TextButton("Cancel", on_click=lambda e: (setattr(dlg, "open", False), self.page.update()))
            ]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()


class PurchasesScreen(ft.Column):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.spacing = 0
        self.po_tab = PurchaseOrderTab()
        self.controls = [self.po_tab]

    def did_mount(self):
        self.po_tab.did_mount()

