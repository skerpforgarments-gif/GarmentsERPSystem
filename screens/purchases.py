import flet as ft
import uuid
import math
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
from components.size_matrix import sort_sizes
from core.pdf_gen import pdf_engine, print_pdf
import os


class SimpleSizeMatrixModal(ft.AlertDialog):
    def __init__(self, item_name, available_sizes, current_values, on_save):
        super().__init__()
        self.on_save = on_save
        self.modal = True
        self.title = ft.Text(f"Enter Sizes for: {item_name}", size=16, weight="bold")
        
        self.size_tfs = {}
        controls = []
        for s in available_sizes:
            tf = ft.TextField(
                label=s,
                value=str(current_values.get(s, "")),
                width=80,
                height=45,
                text_align=ft.TextAlign.CENTER,
                keyboard_type=ft.KeyboardType.NUMBER
            )
            self.size_tfs[s] = tf
            controls.append(tf)
            
        self.content = ft.Container(
            width=500,
            content=ft.Row(controls, wrap=True, spacing=10)
        )
        
        self.actions = [
            ft.TextButton("Cancel", on_click=lambda e: self.close_modal()),
            ft.ElevatedButton("Save", bgcolor=AppColors.PRIMARY, color=ft.colors.WHITE, on_click=self.save_clicked)
        ]

    def save_clicked(self, e):
        result = {}
        for s, tf in self.size_tfs.items():
            if tf.value and tf.value.isdigit() and int(tf.value) > 0:
                result[s] = int(tf.value)
        self.on_save(result)
        self.close_modal()
        
    def close_modal(self):
        self.open = False
        self.page.update()

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
        self.po_no      = ft.TextField(label="PO No", width=150, **AppStyles.get_input_style())
        self.po_date    = ft.TextField(label="Date", width=140, value=date.today().isoformat(), **AppStyles.get_input_style())
        self.supplier_dd = ft.Dropdown(label="Select Supplier (Party) *", width=300, on_change=self.on_supplier_change, **AppStyles.get_input_style())
        self.transporter_dd = ft.Dropdown(label="Transporter", width=220, **AppStyles.get_input_style())
        
        S = AppStyles.get_input_style()
        self.destination = ft.TextField(label="Destination", width=160, **S)
        self.remarks     = ft.TextField(label="Remarks",     width=300, **S)

        # ── Footer controls ───────────────────────────────────
        self.no_of_items_lbl = ft.Text("No. Of Items: 0", size=13, weight="w500")
        self.total_pcs    = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        
        self.trade_disc   = ft.TextField(label="Trade %",  value="0", width=80, on_change=self.on_calc_change, **S)
        self.td_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.taxable_value = ft.Text("Taxable: ₹0.00",   size=14, weight="bold")
        self.gst_amount    = ft.Text("GST (5%): ₹0.00",  size=13, color=AppColors.TEXT_SUB)
        self.round_off     = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self.on_calc_change, **S)
        self.gross_amount  = ft.Text("Total: ₹0.00",      size=20, weight="bold", color=AppColors.PRIMARY)

        # ── Scrollable items area ─────────────────────────────
        self.items_col = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0
        )

        self.controls = [
            self._build_header(),
            self._build_col_header(),
            self.items_col,
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
                # Row 1: Title and Order Info
                ft.Row([
                    ft.Row([
                        ft.Text("Purchase Order Entry", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15),
                    ft.Row([self.po_no, self.po_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Supplier and Logistic Info
                ft.Row([
                    self.supplier_dd, self.transporter_dd, self.destination, self.remarks
                ], spacing=12, wrap=True),
            ], spacing=15)
        )

    def _build_col_header(self):
        return ft.Container(
            bgcolor="#F8FAFC",
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            border=ft.border.only(top=ft.border.BorderSide(1, "#E2E8F0"), bottom=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Row([
                ft.Text("Item Details", width=250, weight="bold", size=12, color=AppColors.TEXT_SUB),
                ft.Text("Sizes", width=150, weight="bold", size=12, color=AppColors.TEXT_SUB),
                ft.Text("Rate", width=100, weight="bold", size=12, color=AppColors.TEXT_SUB),
                ft.Text("Qty (Pcs)", width=100, weight="bold", size=12, color=AppColors.TEXT_SUB),
                ft.Text("Amount", width=100, weight="bold", size=12, color=AppColors.TEXT_SUB),
                ft.Container(expand=True),
                ft.ElevatedButton("Add Item", icon=ft.icons.ADD, bgcolor=AppColors.PRIMARY, color=ft.colors.WHITE, 
                                  height=32, on_click=self.add_item_row)
            ])
        )

    def _build_footer(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            content=ft.Column([
                ft.Row([
                    ft.Column([self.no_of_items_lbl, self.total_pcs], spacing=2),
                    ft.VerticalDivider(width=20),
                    ft.Column([self.trade_disc, self.td_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(expand=True),
                    ft.Column([self.taxable_value, self.gst_amount], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                    self.round_off,
                    ft.Column([
                        self.gross_amount,
                        ft.ElevatedButton(
                            "Confirm & Save PO", icon=ft.icons.CHECK_CIRCLE,
                            bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE,
                            height=45, on_click=self.save_po
                        )
                    ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ])
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

    def on_supplier_change(self, e):
        pass

    # ─────────────────────────────────────────────────────────
    # Row Management
    # ─────────────────────────────────────────────────────────
    def add_item_row(self, e):
        row_id = str(uuid.uuid4())
        
        items_data = select("items", {"company_id": state.company_id, "item_type": ["Supplies", "Both"]})
        for it in items_data:
            self.all_items_metadata[str(it["id"])] = it

        item_dd = ft.Dropdown(
            options=[ft.dropdown.Option(str(it["id"]), it["item_name"]) for it in items_data],
            width=250,
            **AppStyles.get_input_style()
        )
        
        size_lbl  = ft.Text("-", width=150, size=12, color=AppColors.TEXT_SUB)
        rate_tf   = ft.TextField(value="0", width=100, on_change=self.on_calc_change, **AppStyles.get_input_style())
        qty_tf    = ft.TextField(value="0", width=100, read_only=True, **AppStyles.get_input_style())
        amt_lbl   = ft.Text("₹0.00", width=100, size=13, weight="w500")

        size_qty_map = {}

        def _open_matrix(e):
            if not item_dd.value:
                self.page.snack_bar = ft.SnackBar(ft.Text("Select an item first!"), bgcolor="red")
                self.page.snack_bar.open = True
                self.page.update()
                return

            meta = self.all_items_metadata.get(item_dd.value, {})
            avail_sizes = meta.get("sizes", [])
            if not avail_sizes:
                avail_sizes = ["FS"]
                
            avail_sizes = sort_sizes(avail_sizes)
            
            def _on_matrix_save(new_map):
                size_qty_map.clear()
                size_qty_map.update(new_map)
                
                tot_qty = sum(new_map.values())
                sz_str  = ", ".join(f"{s}:{q}" for s, q in new_map.items() if q > 0)
                
                qty_tf.value = str(tot_qty)
                size_lbl.value = sz_str if sz_str else "-"
                
                self.on_calc_change(None)
            
            self.matrix_modal = SimpleSizeMatrixModal(
                item_name=meta.get("item_name", "Item"),
                available_sizes=avail_sizes,
                current_values=size_qty_map,
                on_save=_on_matrix_save
            )
            self.page.overlay.append(self.matrix_modal)
            self.matrix_modal.open = True
            self.page.update()

        btn_matrix = ft.IconButton(ft.icons.GRID_ON, icon_color=AppColors.PRIMARY, on_click=_open_matrix, tooltip="Enter Sizes")
        btn_del    = ft.IconButton(ft.icons.DELETE_OUTLINE, icon_color=ft.colors.RED_400, tooltip="Remove Row")

        row = ft.Container(
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                item_dd, size_lbl, rate_tf, qty_tf, amt_lbl,
                ft.Container(expand=True),
                btn_matrix, btn_del
            ])
        )

        item_data = {
            "id": row_id,
            "row_control": row,
            "item_dd": item_dd,
            "size_lbl": size_lbl,
            "rate_tf": rate_tf,
            "qty_tf": qty_tf,
            "amt_lbl": amt_lbl,
            "size_qty_map": size_qty_map
        }

        def _remove(e):
            self.order_items.remove(item_data)
            self.items_col.controls.remove(row)
            self.on_calc_change(None)

        btn_del.on_click = _remove
        item_dd.on_change = lambda e: self.on_calc_change(None)

        self.order_items.append(item_data)
        self.items_col.controls.append(row)
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # Calculations
    # ─────────────────────────────────────────────────────────
    def on_calc_change(self, e):
        total_pcs = 0
        gross_sum = 0

        for it in self.order_items:
            try:
                r = float(it["rate_tf"].value or 0)
                q = float(it["qty_tf"].value or 0)
                amt = r * q
                it["amt_lbl"].value = f"₹{amt:,.2f}"
                total_pcs += q
                gross_sum += amt
            except: pass

        # Apply Discount
        td_p = float(self.trade_disc.value or 0)
        td_amt = gross_sum * (td_p / 100)
        self.td_amt_lbl.value = f"Amt: ₹{td_amt:,.2f}"
        
        taxable = gross_sum - td_amt
        gst = taxable * 0.05 # Default 5% for purchases for now
        
        subtotal = taxable + gst
        final_amt = math.ceil(subtotal)
        roff = final_amt - subtotal
        
        self.no_of_items_lbl.value = f"No. Of Items: {len([i for i in self.order_items if i['item_dd'].value])}"
        self.total_pcs.value = f"Total Pcs: {int(total_pcs)}"
        self.taxable_value.value = f"Taxable: ₹{taxable:,.2f}"
        self.gst_amount.value = f"GST (5%): ₹{gst:,.2f}"
        self.round_off.value = f"{roff:.2f}"
        self.gross_amount.value = f"Total: ₹{final_amt:,.2f}"

        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # Save Logic
    # ─────────────────────────────────────────────────────────
    def save_po(self, e):
        if not state.company_id: return
        if not self.supplier_dd.value:
            self._snack("Please select a Supplier!", "red")
            return

        valid_items = []
        for it in self.order_items:
            if not it["item_dd"].value: continue
            for sz, q in it["size_qty_map"].items():
                if q > 0:
                    valid_items.append({
                        "item_id": it["item_dd"].value,
                        "size_value": sz,
                        "qty": q,
                        "rate": float(it["rate_tf"].value or 0)
                    })

        if not valid_items:
            self._snack("No items to save!", "red")
            return

        try:
            po_id = self.current_edit_id or str(uuid.uuid4())
            header = {
                "company_id":     state.company_id,
                "po_no":          self.po_no.value,
                "po_date":        self.po_date.value,
                "supplier_id":    self.supplier_dd.value,
                "transporter_id": self.transporter_dd.value or None,
                "destination":    self.destination.value,
                "remarks":        self.remarks.value,
                "total_pcs":      int(float(self.total_pcs.value.split(": ")[1])),
                "total_amount":   float(self.gross_amount.value.replace("Total: ₹", "").replace(",", "")),
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
                    "size_value":      item["size_value"],
                    "rate":            item["rate"],
                    "qty_pieces":      int(item["qty"]),
                    "amount":          item["qty"] * item["rate"],
                })

            # Update Ledger (Credit the supplier)
            insert("ledger_entries", {
                "company_id":   state.company_id,
                "account_id":   self.supplier_dd.value,
                "account_type": "Party",
                "debit":        0,
                "credit":       header["total_amount"],
                "ref_id":       header["po_no"],
                "ref_type":     "Purchase Order",
                "entry_date":   header["po_date"]
            })

            self._snack("✅ Purchase Order Saved and Ledger updated!", "green")
            self.clear_form()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    def clear_form(self, e=None):
        self.current_edit_id = None
        self.po_no.value = get_next_doc_no("purchase_orders", "PO", state.company_id, "po_no")
        self.supplier_dd.value = None
        self.transporter_dd.value = None
        self.destination.value = ""
        self.remarks.value = ""
        self.order_items = []
        self.items_col.controls = []
        self.add_item_row(None)
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
                        ft.IconButton(ft.icons.PRINT, on_click=lambda e, o=ord: self.print_history_po(o))
                    ])
                )
            )
        dlg = ft.AlertDialog(title=ft.Text("PO History"), content=ft.Container(lv, width=600, height=400))
        self.page.overlay.append(dlg); dlg.open = True; self.page.update()

    def print_history_po(self, order):
        items = select("purchase_order_items", {"purchase_order_id": order["id"]})
        for it in items:
            i_data = select("items", {"id": it["item_id"]})
            it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"
        comp = select("companies", {"id": state.company_id})
        pdf_path = pdf_engine.generate_order(order, items, comp[0] if comp else {})
        print_pdf(pdf_path)

class PurchasesScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 10
        self.po_tab = PurchaseOrderTab()
        self.content = ft.Column([
            ft.Tabs(selected_index=0, tabs=[ft.Tab(text="Purchase Orders")]),
            self.po_tab
        ], expand=True)

    def did_mount(self):
        self.po_tab.did_mount()
