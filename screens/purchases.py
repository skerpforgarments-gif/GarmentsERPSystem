import flet as ft
import uuid
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert
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
            content=ft.Row([
                # Left side: Summary counts
                ft.Column([
                    self.no_of_items_lbl,
                    self.total_pcs,
                ], spacing=5),
                
                # Right side: Amount and Save
                ft.Row([
                    self.gross_amount,
                    ft.ElevatedButton(
                        "Confirm & Save PO",
                        icon=ft.icons.CHECK_CIRCLE,
                        bgcolor=ft.colors.GREEN_600,
                        color=ft.colors.WHITE,
                        height=45,
                        on_click=self.save_po
                    )
                ], spacing=20, alignment=ft.MainAxisAlignment.END)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    # ─────────────────────────────────────────────────────────
    # Lifecycle & Loaders
    # ─────────────────────────────────────────────────────────
    def did_mount(self):
        if not state.company_id:
            return
        self.po_no.value = f"PO-{uuid.uuid4().hex[:6].upper()}"
        self.load_dropdowns()
        self.add_item_row(None)

    def load_dropdowns(self):
        parties = select("parties", {"company_id": state.company_id})
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
        item_id = str(uuid.uuid4())
        
        items_data = select("items", {"company_id": state.company_id})
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

        # Hidden dict holding matrix sizes: { "M": 10, "L": 20 }
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
                
                # Update displays
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
            "id": item_id,
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
        total_p = 0
        gross   = 0

        for it in self.order_items:
            try:
                r = float(it["rate_tf"].value or 0)
                q = float(it["qty_tf"].value or 0)
                amt = r * q
                it["amt_lbl"].value = f"₹{amt:,.2f}"
                total_p += q
                gross += amt
            except:
                pass

        self.no_of_items_lbl.value = f"No. Of Items: {len([i for i in self.order_items if i['item_dd'].value])}"
        self.total_pcs.value = f"Total Pcs: {int(total_p)}"
        self.gross_amount.value = f"Total: ₹{gross:,.2f}"

        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # Save Logic
    # ─────────────────────────────────────────────────────────
    def save_po(self, e):
        if not state.company_id:
            self.page.snack_bar = ft.SnackBar(ft.Text("Company not selected!"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        if not self.supplier_dd.value:
            self.page.snack_bar = ft.SnackBar(ft.Text("Please select a Supplier!"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()
            return

        valid_items = []
        gross = 0
        total_p = 0
        for it in self.order_items:
            if not it["item_dd"].value: continue
            
            # Split the map into distinct rows
            for sz, q in it["size_qty_map"].items():
                if q > 0:
                    r = float(it["rate_tf"].value or 0)
                    amt = r * q
                    gross += amt
                    total_p += q
                    valid_items.append({
                        "item_id": it["item_dd"].value,
                        "sizes_label": sz,
                        "qty": q,
                        "rate": r
                    })

        if not valid_items:
            self.page.snack_bar = ft.SnackBar(ft.Text("No valid items with quantities to save!"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()
            return

        try:
            # 1. Insert Header
            po_id = str(uuid.uuid4())
            header_data = {
                "id":             po_id,
                "company_id":     state.company_id,
                "po_no":          self.po_no.value,
                "po_date":        self.po_date.value,
                "supplier_id":    self.supplier_dd.value,
                "transporter_id": self.transporter_dd.value if self.transporter_dd.value else None,
                "destination":    self.destination.value,
                "remarks":        self.remarks.value,
                "total_pcs":      int(total_p),
                "total_amount":   gross,
                "status":         "Pending"
            }
            insert("purchase_orders", header_data)

            # 2. Insert Items
            for item in valid_items:
                insert("purchase_order_items", {
                    "purchase_order_id": po_id,
                    "company_id":      state.company_id,
                    "item_id":         item["item_id"],
                    "size_value":      item["sizes_label"],
                    "rate":            item["rate"],
                    "qty_pieces":      int(item["qty"]),
                    "amount":          item["qty"] * item["rate"],
                })

            # Fetch the saved order to generate PDF
            saved_order = select("purchase_orders", {"id": po_id})
            if saved_order:
                order_data = saved_order[0]
                p_data = select("parties", {"id": order_data["supplier_id"]})
                if p_data:
                    order_data["party_name"] = p_data[0]["name"]
                
                # We need all items for PDF
                o_items = select("purchase_order_items", {"purchase_order_id": po_id})
                for o_it in o_items:
                    if not o_it.get("item_name"):
                        i_data = select("items", {"id": o_it["item_id"]})
                        o_it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"

                comp_data = select("companies", {"id": state.company_id})
                company = comp_data[0] if comp_data else {}
                
                # Reusing the order PDF generator, but we will pass PO mode if needed.
                # For now, generate_order is generic enough.
                pdf_path = pdf_engine.generate_order(order_data, o_items, company)
                print_pdf(pdf_path)

            self.page.snack_bar = ft.SnackBar(ft.Text("✅ Purchase Order Saved Successfully!"), bgcolor="green")
            self.page.snack_bar.open = True
            self.clear_form(None)

        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    def clear_form(self, e=None):
        self.po_no.value = f"PO-{uuid.uuid4().hex[:6].upper()}"
        self.supplier_dd.value = None
        self.transporter_dd.value = None
        self.destination.value = ""
        self.remarks.value = ""
        self.order_items = []
        self.items_col.controls = []
        self.on_calc_change(None)
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # History Modal
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        orders = select("purchase_orders", {"company_id": state.company_id})
        orders.sort(key=lambda x: x.get("po_date", ""), reverse=True)
        
        parties = select("parties", {"company_id": state.company_id})
        party_map = {str(p["id"]): p["name"] for p in parties}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for ord in orders:
            p_name = party_map.get(str(ord.get("supplier_id")), "Unknown")
            ord["party_name"] = p_name
            
            lv.controls.append(
                ft.Container(
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{ord.get('po_no')}  |  {ord.get('po_date')}", weight="bold", size=14),
                            ft.Text(p_name, size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"Pcs: {ord.get('total_pcs', 0)}", size=12),
                        ft.Text(f"₹ {float(ord.get('total_amount', 0)):,.2f}", size=14, weight="bold", color=AppColors.PRIMARY),
                        ft.IconButton(ft.icons.PRINT, tooltip="Print PO", icon_color=ft.colors.BLUE_700, 
                                      on_click=lambda e, o=ord: self.print_history_po(o))
                    ])
                )
            )
            
        dlg = ft.AlertDialog(
            title=ft.Text("Recent Purchase Orders", size=18, weight="bold"),
            content=ft.Container(lv, width=600, height=400),
            actions=[ft.TextButton("Close", on_click=lambda e: self.close_modal(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def close_modal(self, dlg):
        dlg.open = False
        self.page.update()
        self.page.overlay.remove(dlg)

    def print_history_po(self, order):
        try:
            items = select("purchase_order_items", {"purchase_order_id": order["id"]})
            for o_it in items:
                if not o_it.get("item_name"):
                    i_data = select("items", {"id": o_it["item_id"]})
                    o_it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"

            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            # Temporary mapping for generate_order template
            order["order_no"] = order.get("po_no")
            order["order_date"] = order.get("po_date")
            
            pdf_path = pdf_engine.generate_order(order, items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Print Error: {ex}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

class PurchasesScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 10
        
        self.tabs = ft.Tabs(
            selected_index=0,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            divider_color="#F0F0F0",
            tabs=[
                ft.Tab(text="Purchase Orders"),
            ]
        )
        
        self.po_tab = PurchaseOrderTab()
        
        self.content = ft.Column([
            self.tabs,
            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
            self.po_tab
        ], expand=True)

    def did_mount(self):
        # Forward did_mount to tabs
        if hasattr(self.po_tab, 'did_mount'):
            self.po_tab.did_mount()
