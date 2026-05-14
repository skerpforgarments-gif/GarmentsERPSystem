import flet as ft
import uuid
import json
import math
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no
from components.size_matrix import SizeMatrixModal, sort_sizes
from core.pdf_gen import pdf_engine, print_pdf
import os


class OrderEntryTab(ft.Column):
    """
    Order Entry Screen — Correct Flet layout for sticky header/footer:

    SalesScreen (ft.Column, expand=True, NO scroll)
    ├── header_card         ← fixed / always visible
    ├── col_header_row      ← fixed / always visible
    ├── self.items_col      ← ft.Column(scroll=AUTO, expand=True) → scrollable, bounded
    ├── ft.Divider          ← fixed
    └── footer_container    ← fixed / always visible
    """

    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0
        # ⚠ NO self.scroll here — this is the outer fixed column

        # --- Data ---
        self.order_items        = []
        self.all_items_metadata = {}
        self.matrix_modal       = None
        self.current_edit_id    = None

        # ── Header controls ───────────────────────────────────
        self.order_no   = ft.TextField(label="Order No", width=150, **AppStyles.get_input_style())
        self.order_date = ft.TextField(label="Date", width=140, value=date.today().isoformat(), **AppStyles.get_input_style())
        self.party_dd   = ft.Dropdown(label="Select Party *", width=300, on_change=self.on_party_change, **AppStyles.get_input_style())
        self.agent_dd   = ft.Dropdown(label="Agent", width=180, **AppStyles.get_input_style())
        self.transporter_dd = ft.Dropdown(label="Transporter", width=220, **AppStyles.get_input_style())
        self.price_list_dd  = ft.Dropdown(label="Price List",  width=180, **AppStyles.get_input_style())
        self.price_type_dd  = ft.Dropdown(
            label="Type", width=120, value="Wholesale",
            options=[ft.dropdown.Option(k) for k in ("Wholesale", "Retail", "MRP")],
            on_change=self.on_price_type_change,
            **AppStyles.get_input_style()
        )
        self.qty_type = ft.SegmentedButton(
            segments=[ft.Segment(value="pcs", label=ft.Text("Pcs")),
                      ft.Segment(value="box", label=ft.Text("Box"))],
            selected={"pcs"}, on_change=self.on_qty_type_change,
        )
        S = AppStyles.get_input_style()
        self.destination = ft.TextField(label="Destination", width=160, **S)
        self.order_by    = ft.TextField(label="Order By",    width=140, **S)
        self.order_thro  = ft.Dropdown(label="Order Thro'",  width=140, value="DIRECT", options=[ft.dropdown.Option("DIRECT"), ft.dropdown.Option("AGENT")], **S)
        self.party_order_no = ft.TextField(label="Party Order No", width=140, **S)
        self.party_order_dt = ft.TextField(label="Party Order Dt", width=140, value=date.today().isoformat(), **S)
        self.remarks     = ft.TextField(label="Remarks",     width=300, **S)
        self.no_of_cases = ft.TextField(label="No of Cases", width=100, value="1", keyboard_type=ft.KeyboardType.NUMBER, **S)
        self.docs_by     = ft.RadioGroup(content=ft.Row([
            ft.Text("Docs By:", size=12, weight="bold"),
            ft.Radio(value="Direct", label="Direct"),
            ft.Radio(value="Bank",   label="Bank"),
        ], spacing=10), value="Direct")

        # Party-level tax rates
        self._party_gst_rate  = 5.0
        self._party_tax_type  = "GST"
        self._party_tcs_rate  = 0.0
        self._party_cess_rate = 0.0
        self._party_cgst_rate = 0.0
        self._party_sgst_rate = 0.0
        self._party_igst_rate = 0.0
        self._party_tcs_appl  = False

        # ── Footer controls ───────────────────────────────────
        self.no_of_items_lbl = ft.Text("No. Of Items: 0", size=13, weight="w500")
        self.total_pcs    = ft.Text("Total Pcs: 0",    size=13, weight="bold")
        self.total_boxes  = ft.Text("Total Boxes: 0",  size=13, weight="bold")
        self.total_units  = ft.Text("Total Units: 0",  size=13, weight="bold")
        
        S = AppStyles.get_input_style()
        self.trade_disc   = ft.TextField(label="Trade %",  value="0", width=80, on_change=self.on_calc_change, **S)
        self.td_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.scheme_disc  = ft.TextField(label="Scheme %", value="0", width=80, on_change=self.on_calc_change, **S)
        self.spd_amt_lbl  = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.fest_disc    = ft.TextField(label="Fest %",   value="0", width=80, on_change=self.on_calc_change, **S)
        self.fd_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.spec_disc    = ft.TextField(label="Spec %",   value="0", width=80, on_change=self.on_calc_change, **S)
        self.scd_amt_lbl  = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        self.cash_disc    = ft.TextField(label="Cash %",   value="0", width=80, on_change=self.on_calc_change, **S)
        self.cd_amt_lbl   = ft.Text("Amt: ₹0.00", size=11, color=AppColors.TEXT_SUB)
        
        # --- Dynamic discount ordering ---
        self.DEFAULT_DISCOUNT_ORDER = ["trade", "scheme", "festival", "scd", "cd"]
        self.DISCOUNT_MAP = {
            "trade":    {"field": self.trade_disc,  "amt": self.td_amt_lbl,  "label": "Trade %"},
            "scheme":   {"field": self.scheme_disc, "amt": self.spd_amt_lbl, "label": "Scheme %"},
            "festival": {"field": self.fest_disc,   "amt": self.fd_amt_lbl,  "label": "Fest %"},
            "scd":      {"field": self.spec_disc,   "amt": self.scd_amt_lbl, "label": "Spec %"},
            "cd":       {"field": self.cash_disc,   "amt": self.cd_amt_lbl,  "label": "Cash %"},
        }
        self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self.discount_row = ft.Row(spacing=15)  # Dynamically reordered
        self._reorder_discount_fields()
        
        self.tax_type_dd = ft.Dropdown(
            label="Tax Type",
            options=[ft.dropdown.Option("GST"), ft.dropdown.Option("IGST")],
            value="GST",
            width=120,
            on_change=self.on_calc_change
        )
        self.taxable_value = ft.Text("Taxable: ₹0.00",   size=13, weight="bold")
        self.gst_rate_tf   = ft.TextField(label="GST %", value="5", width=60, on_change=self.on_calc_change, **S)
        
        self.cgst_rate_tf  = ft.TextField(label="CGST %", value="0", width=60, on_change=self.on_calc_change, **S)
        self.cgst_amt_lbl  = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.sgst_rate_tf  = ft.TextField(label="SGST %", value="0", width=60, on_change=self.on_calc_change, **S)
        self.sgst_amt_lbl  = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.igst_rate_tf  = ft.TextField(label="IGST %", value="0", width=60, on_change=self.on_calc_change, visible=False, **S)
        self.igst_amt_lbl  = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB, visible=False)
        
        self.cess_rate_tf  = ft.TextField(label="Cess %", value="0", width=60, on_change=self.on_calc_change, **S)
        self.cess_amt_lbl  = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        
        self.tcs_rate_tf   = ft.TextField(label="TCS %",  value="0", width=60, on_change=self.on_calc_change, **S)
        self.tcs_amt_lbl   = ft.Text("Amt: ₹0.00", size=10, color=AppColors.TEXT_SUB)
        self.gst_amount    = ft.Text("Total GST: ₹0.00",  size=12, color=AppColors.TEXT_SUB)
        self.round_off     = ft.TextField(label="Round Off", value="0.00", width=100, on_change=lambda e: self.update_totals(e.control), **S)
        self.gross_amount  = ft.Text("Total: ₹0.00",      size=20, weight="bold", color=AppColors.PRIMARY)

        # ── Scrollable items area ─────────────────────────────
        # expand=True here is BOUNDED because the parent (SalesScreen) has a fixed
        # height (it fills content_area without scrolling). This is correct.
        self.items_col = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

        # ── Assemble the full layout ──────────────────────────
        self.controls = [
            self._build_header(),
            self._build_col_header(),
            self.items_col,        # ← scrollable, expands to fill remaining space
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
                        ft.Text("Order Entry", size=22, weight="bold", color=AppColors.PRIMARY),
                        ft.OutlinedButton("View History", icon=ft.icons.HISTORY, on_click=self.show_history_modal, style=ft.ButtonStyle(color=AppColors.PRIMARY))
                    ], spacing=15),
                    ft.Row([self.order_no, self.order_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Party and Logistic Info
                ft.Row([
                    self.party_dd, self.agent_dd, self.transporter_dd, self.destination,
                ], spacing=12, wrap=True),
                
                # Row 3: Pricing and Order Source
                ft.Row([
                    self.price_list_dd, self.price_type_dd, self.party_order_no, self.party_order_dt,
                    self.order_by, self.order_thro,
                ], spacing=12, wrap=True),

                # Row 4: Remarks and Type
                ft.Row([
                    self.remarks, self.no_of_cases,
                    ft.Column([ft.Text("Qty Type", size=10, weight="bold"), self.qty_type], spacing=4),
                    ft.VerticalDivider(width=20),
                    self.docs_by,
                ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
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
                ft.Text("IC CODE / ITEM NAME", width=250, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("SIZE",              width=100, size=11, weight="bold", color=AppColors.TEXT_SUB),
                ft.Text("QTY",               width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("TOT PCS",           width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("BOXES",             width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("RATE",              width=100, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("DISC %",            width=80,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("AMOUNT",            expand=True, size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.RIGHT),
                ft.Text("ACT",               width=60,  size=11, weight="bold", color=AppColors.TEXT_SUB, text_align=ft.TextAlign.CENTER),
            ], spacing=0)
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
                        ft.Row([self.total_pcs, ft.Text(" | "), self.total_boxes, ft.Text(" | "), self.total_units]),
                    ], spacing=5),
                    ft.Container(expand=True),
                    self.discount_row,
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                # Row 2: Final Totals and Actions
                ft.Row([
                    ft.Column([
                        self.taxable_value, 
                        ft.Row([
                            self.tax_type_dd,
                            self.gst_rate_tf, 
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.cgst_rate_tf, self.cgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
                            ft.Column([self.sgst_rate_tf, self.sgst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
                            ft.Column([self.igst_rate_tf, self.igst_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.cess_rate_tf, self.cess_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.VerticalDivider(width=1, color="#E2E8F0"),
                            ft.Column([self.tcs_rate_tf, self.tcs_amt_lbl], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            self.gst_amount, 
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
                    ], spacing=2, expand=True),
                    
                    ft.VerticalDivider(width=1, color="#E2E8F0"),
                    
                    # Round Off Section
                    ft.Column([
                        self.round_off,
                        ft.Row([
                            ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.load_metadata(), tooltip="Refresh Metadata", icon_size=16),
                            ft.Text("Refresh", size=10, color=AppColors.TEXT_SUB),
                        ], spacing=0),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    
                    ft.Container(width=20),
                    
                    # Grand Total Section
                    ft.Column([
                        ft.Text("Grand Total", size=11, color=AppColors.TEXT_SUB, weight="w500"),
                        self.gross_amount,
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                    
                    ft.Container(width=10),
                    
                    ft.ElevatedButton(
                        "Confirm & Save",
                        icon=ft.icons.SAVE_ALT,
                        on_click=self.save_order,
                        height=48,
                        style=AppStyles.primary_button_style(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            ], spacing=10),
        )

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────
    def did_mount(self):
        self.load_metadata()

    def load_metadata(self):
        if not state.company_id:
            return
        items = select("items", {"company_id": state.company_id, "item_type": ["Sales", "Both"]})
        self.all_items_metadata = {str(i["id"]): i for i in items}

        self.matrix_modal = SizeMatrixModal(on_submit=self.add_matrix_results)
        if self.page and self.matrix_modal not in self.page.overlay:
            self.page.overlay.append(self.matrix_modal)
            self.page.update()
        self.matrix_modal.load_items(items)

        parties      = select("parties",      {"company_id": state.company_id, "party_type": ["Customer", "Both"]})
        transporters = select("transporters", {"company_id": state.company_id})
        price_lists  = select("price_lists",  {"company_id": state.company_id})
        agents       = select("agents",       {"company_id": state.company_id})

        self.party_dd.options       = [ft.dropdown.Option(key=str(p["id"]), text=p["name"])      for p in parties]
        self.transporter_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"])      for t in transporters]
        self.price_list_dd.options  = [ft.dropdown.Option(key=str(p["id"]), text=p["list_name"]) for p in price_lists]
        self.agent_dd.options       = [ft.dropdown.Option(key=str(a["id"]), text=a["name"])      for a in agents]

        if not self.order_no.value:
            self.order_no.value = get_next_doc_no("orders", "O", state.company_id, "order_no")

        if self.page:
            self.update()

    # ─────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────
    def on_party_change(self, e):
        party_id = self.party_dd.value
        if not party_id:
            return
        data = select("parties", {"id": party_id})
        if data:
            p = data[0]
            if p.get("transporter_id"): self.transporter_dd.value = str(p["transporter_id"])
            if p.get("price_list_id"):  self.price_list_dd.value  = str(p["price_list_id"])
            if p.get("price_type"):     self.price_type_dd.value  = p["price_type"]
            if p.get("agent_id"):       self.agent_dd.value       = str(p["agent_id"])
            self.destination.value = p.get("delivery_city") or p.get("billing_city", "")
            # Auto-fill all 5 discount tiers from Party Master
            self.trade_disc.value  = str(p.get("discount_trade",    0))
            self.scheme_disc.value = str(p.get("discount_scheme",   0))
            self.fest_disc.value   = str(p.get("discount_festival", 0))
            self.spec_disc.value   = str(p.get("discount_scd",      0))
            self.cash_disc.value   = str(p.get("discount_cd",       0))
            # Load dynamic discount order
            self._load_discount_order(p.get("discount_order"))
            
            # Load Tax Rates from Party Master
            self.gst_rate_tf.value  = str(p.get("gst_percent", 5) or 5)
            self.tax_type_dd.value  = str(p.get("tax_type", "GST") or "GST").upper()
            self.tcs_rate_tf.value  = str(p.get("tcs_percent", 0) or 0)
            self.cess_rate_tf.value = str(p.get("cess_percent", 0) or 0)
            self._party_tcs_appl    = p.get("tcs_appl", False)
            
            # Load components from party table
            self.cgst_rate_tf.value = str(p.get("cgst_percent", 0) or 0)
            self.sgst_rate_tf.value = str(p.get("sgst_percent", 0) or 0)
            self.igst_rate_tf.value = str(p.get("igst_percent", 0) or 0)
            
            self.update_totals()
            self.update()

    def on_calc_change(self, e=None):
        trigger = e.control if e else None
        
        # 1. Sync CGST/SGST if the main GST rate is changed OR mode switched
        if trigger == self.gst_rate_tf or trigger == self.tax_type_dd:
            val_str = str(self.gst_rate_tf.value or "").strip()
            try:
                if val_str.endswith("."):
                    gst_p = float(val_str + "0")
                else:
                    gst_p = float(val_str or 0)
                
                tax_type = str(self.tax_type_dd.value or "GST").upper()
                if tax_type == "GST":
                    self.cgst_rate_tf.value = f"{gst_p / 2:g}"
                    self.sgst_rate_tf.value = f"{gst_p / 2:g}"
                else:
                    self.igst_rate_tf.value = f"{gst_p:g}"
            except ValueError:
                pass
            
        # 2. Run the main calculation
        self.update_totals(trigger)
        
        # 3. Explicitly update the page to show the new component values
        if self.page:
            self.page.update()

    def on_price_type_change(self, e):
        """Automatically updates all rates in the grid when the Price Type changes."""
        if not self.price_list_dd.value or not self.order_items:
            return
            
        try:
            # 1. Fetch latest prices from master
            prices = select("price_list_items", {"price_list_id": self.price_list_dd.value})
            
            # 2. Build a lookup map: { item_id: { size: rate } }
            rate_key = f"{self.price_type_dd.value.lower()}_rate"
            rate_map = {}
            for p in prices:
                iid = str(p["item_id"])
                if iid not in rate_map: rate_map[iid] = {}
                rate_map[iid][p["size_value"]] = float(p.get(rate_key, 0))
                
            # 3. Update every item currently in the grid
            for item in self.order_items:
                iid = str(item["item_id"])
                # Get the first size from the comma-separated label to determine the new rate
                sizes = [s.strip() for s in item["sizes_label"].split(",")]
                if sizes and iid in rate_map:
                    # Try first size, fallback to 0
                    new_rate = rate_map[iid].get(sizes[0], 0)
                    item["rate"] = new_rate

            # 4. Refresh UI
            self.rebuild_grid()
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Switched to {self.price_type_dd.value} pricing"), bgcolor=AppColors.INFO)
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            print(f"Price Switch Error: {ex}")

    # ─── Dynamic Discount Order Helpers ──────────────────────
    def _reorder_discount_fields(self):
        """Rebuild the discount_row with columns in the current _discount_order."""
        self.discount_row.controls = []
        for key in self._discount_order:
            meta = self.DISCOUNT_MAP.get(key)
            if meta:
                self.discount_row.controls.append(
                    ft.Column([meta["field"], meta["amt"]],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
                )

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
            # Validate all 5 keys are present
            if set(order) == set(self.DEFAULT_DISCOUNT_ORDER) and len(order) == 5:
                self._discount_order = order
            else:
                self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        else:
            self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self._reorder_discount_fields()

    def on_qty_type_change(self, e):
        self.rebuild_grid()

    def open_size_matrix(self, e):
        if not self.price_list_dd.value:
            self.page.snack_bar = ft.SnackBar(ft.Text("Please select a Price List first!"), bgcolor="orange")
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        self.matrix_modal.reset()
        self.matrix_modal.price_list_id = self.price_list_dd.value
        self.matrix_modal.price_type    = self.price_type_dd.value or "Wholesale"
        self.matrix_modal.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────
    # Grid
    # ─────────────────────────────────────────────────────────
    def add_matrix_results(self, results):
        """Group sizes by rate (Tirupur convention) and append to order."""
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
                "disc_p":      0.0,
            })
        self.rebuild_grid()

    def _make_row(self, item):
        meta  = self.all_items_metadata.get(str(item["item_id"]), {})
        inner = meta.get("pcs_per_inner_box",  1) or 1
        outer = meta.get("boxes_per_outer_box", 1) or 1
        is_box = self.qty_type.selected == {"box"}
        tax_rate = self._party_gst_rate

        # Dynamic labels for real-time updates
        pcs_lbl     = ft.Text("", width=80,  size=13, text_align=ft.TextAlign.RIGHT)
        boxes_lbl   = ft.Text("", width=80,  size=13, text_align=ft.TextAlign.RIGHT)
        taxable_lbl = ft.Text("", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY)

        def update_labels():
            pcs   = item["qty"] * inner * outer if is_box else item["qty"]
            boxes = item["qty"] if is_box else pcs / (inner * outer)
            amount  = pcs * item["rate"]
            disc    = amount * (item.get("disc_p", 0) / 100)
            taxable = amount - disc

            pcs_lbl.value     = str(int(pcs))
            boxes_lbl.value   = f"{boxes:.1f}"
            taxable_lbl.value = f"₹{taxable:,.2f}"
            
            # Store calculated taxable amount for global update_totals
            item["amount"] = taxable
            
            if pcs_lbl.page:
                pcs_lbl.update(); boxes_lbl.update(); taxable_lbl.update()

        def update_item_field(f, v):
            try:
                if f == "qty": item["qty"] = int(v or 0)
                elif f == "rate": item["rate"] = float(v or 0)
                elif f == "disc_p": item["disc_p"] = float(v or 0)
                update_labels()
                self.update_totals()
            except ValueError: pass

        update_labels() # Initial population

        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                ft.Text(item["item_name"],        width=250, size=13, weight="w500"),
                ft.Text(item["sizes_label"],      width=100, size=11, color=AppColors.PRIMARY, italic=True),
                
                ft.Container(
                    width=80, content=ft.TextField(
                        value=str(item["qty"]), text_align=ft.TextAlign.RIGHT,
                        on_change=lambda e: update_item_field("qty", e.control.value), 
                        **{**AppStyles.get_input_style(), "height": 35}
                    )
                ),
                
                pcs_lbl,
                boxes_lbl,
                
                ft.Container(
                    width=100, content=ft.TextField(
                        value=str(item["rate"]), text_align=ft.TextAlign.RIGHT,
                        on_change=lambda e: update_item_field("rate", e.control.value), 
                        **{**AppStyles.get_input_style(), "height": 35}
                    )
                ),
                
                ft.Container(
                    width=80, content=ft.TextField(
                        value=str(item["disc_p"]), text_align=ft.TextAlign.RIGHT,
                        on_change=lambda e: update_item_field("disc_p", e.control.value), 
                        **{**AppStyles.get_input_style(), "height": 35}
                    )
                ),
                
                taxable_lbl,
                
                ft.Container(
                    width=60, content=ft.IconButton(
                        ft.icons.DELETE_OUTLINE, icon_color="red400", icon_size=18,
                        on_click=lambda _: self.remove_item(item)
                    ), alignment=ft.alignment.center
                )
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def remove_item(self, item):
        self.order_items.remove(item)
        self.rebuild_grid()

    def rebuild_grid(self):
        self.items_col.controls = [self._make_row(item) for item in self.order_items]
        self.update_totals()
        if self.page:
            self.items_col.update()

    # ─────────────────────────────────────────────────────────
    # Totals
    # ─────────────────────────────────────────────────────────
    def update_totals(self, trigger=None):
        total_pcs = total_boxes = base_sum = 0
        for item in self.order_items:
            meta  = self.all_items_metadata.get(str(item["item_id"]), {})
            inner = meta.get("pcs_per_inner_box",  1) or 1
            outer = meta.get("boxes_per_outer_box", 1) or 1
            is_box = self.qty_type.selected == {"box"}
            pcs   = item["qty"] * inner * outer if is_box else item["qty"]
            boxes = item["qty"] if is_box else pcs / (inner * outer)
            amount = pcs * item["rate"]
            disc   = amount * (item.get("disc_p", 0) / 100)
            total_pcs   += pcs
            total_boxes += boxes
            base_sum    += (amount - disc)

        try:
            tax_on_gross = state.settings.get("tax_on_gross", False)
            gst_rate = float(self.gst_rate_tf.value or 0)
            
            if tax_on_gross:
                # 1. Base + GST = Taxed Total
                gst_amt = base_sum * (gst_rate / 100)
                running_total = base_sum + gst_amt
                
                # 2. Sequential discounts on Taxed Total
                for key in self._discount_order:
                    meta = self.DISCOUNT_MAP.get(key)
                    if meta:
                        d = float(meta["field"].value or 0)
                        disc_amt = running_total * (d / 100)
                        if "amt" in meta:
                            meta["amt"].value = f"Amt: ₹{disc_amt:,.2f}"
                        running_total -= disc_amt
                
                final_taxable = base_sum # In this mode, taxable is just the base sum
                grand_total = running_total
                
            else:
                # 1. Base -> Sequential Discounts = Discounted Total
                running_total = base_sum
                for key in self._discount_order:
                    meta = self.DISCOUNT_MAP.get(key)
                    if meta:
                        d = float(meta["field"].value or 0)
                        disc_amt = running_total * (d / 100)
                        if "amt" in meta:
                            meta["amt"].value = f"Amt: ₹{disc_amt:,.2f}"
                        running_total -= disc_amt
                
                # 2. GST on Discounted Total
                final_taxable = running_total
                gst_amt = final_taxable * (gst_rate / 100)
                grand_total = final_taxable + gst_amt
            
            # Mandatory Tax Rule (Mandate 2025/2026):
            # Only suggest rate if it's currently empty/zero AND the user isn't actively typing in it
            if self.order_items and trigger != self.gst_rate_tf:
                max_rate = max(item.get("rate", 0) for item in self.order_items)
                mandated_rate = 18.0 if max_rate > 2500 else 5.0
                
                curr_val = float(self.gst_rate_tf.value or 0)
                if curr_val == 0:
                    self.gst_rate_tf.value = str(mandated_rate)
                    tax_type = str(self.tax_type_dd.value or "GST").upper()
                    if tax_type == "GST":
                        self.cgst_rate_tf.value = str(mandated_rate / 2)
                        self.sgst_rate_tf.value = str(mandated_rate / 2)
                    else:
                        self.igst_rate_tf.value = str(mandated_rate)

            tax_label = str(self.tax_type_dd.value or "GST").upper()
            
            # Use specific component rates from party table if available
            if tax_label == "IGST":
                self.igst_rate_tf.visible = self.igst_amt_lbl.visible = True
                self.cgst_rate_tf.visible = self.cgst_amt_lbl.visible = False
                self.sgst_rate_tf.visible = self.sgst_amt_lbl.visible = False
                
                i_rate = float(self.igst_rate_tf.value or 0)
                actual_tax = final_taxable * (i_rate/100)
                self.igst_amt_lbl.value = f"Amt: ₹{actual_tax:,.2f}"
            else:
                self.igst_rate_tf.visible = self.igst_amt_lbl.visible = False
                self.cgst_rate_tf.visible = self.cgst_amt_lbl.visible = True
                self.sgst_rate_tf.visible = self.sgst_amt_lbl.visible = True
                
                c_rate = float(self.cgst_rate_tf.value or 0)
                s_rate = float(self.sgst_rate_tf.value or 0)
                actual_tax = (final_taxable * (c_rate/100)) + (final_taxable * (s_rate/100))
                self.cgst_amt_lbl.value = f"Amt: ₹{final_taxable * (c_rate/100):,.2f}"
                self.sgst_amt_lbl.value = f"Amt: ₹{final_taxable * (s_rate/100):,.2f}"

            # CESS calculation (on Taxable Value)
            c_rate = float(self.cess_rate_tf.value or 0)
            actual_cess = final_taxable * (c_rate / 100)
            self.cess_amt_lbl.value = f"Amt: ₹{actual_cess:,.2f}"

            # Re-run the mode-specific final total
            if tax_on_gross:
                # If Tax on Gross: Total = (Base + Actual_Tax + Cess) -> Discounts
                running_total = base_sum + actual_tax + actual_cess
                for key in self._discount_order:
                    meta = self.DISCOUNT_MAP.get(key)
                    if meta:
                        d = float(meta["field"].value or 0)
                        running_total -= (running_total * (d/100))
                sub_total = running_total
            else:
                # If Tax on Net: Total = (Base -> Discounts) + Actual_Tax + Cess
                running_total = base_sum
                for key in self._discount_order:
                    meta = self.DISCOUNT_MAP.get(key)
                    if meta:
                        d = float(meta["field"].value or 0)
                        running_total -= (running_total * (d/100))
                sub_total = running_total + actual_tax + actual_cess

            # TCS calculation (on sub_total)
            # Law: Apply only if TCS Applicable is checked for the party in Masters
            actual_tcs = 0
            if getattr(self, '_party_tcs_appl', False):
                t_rate = float(self.tcs_rate_tf.value or 0)
                actual_tcs = sub_total * (t_rate / 100)
                self.tcs_amt_lbl.value = f"Amt: ₹{actual_tcs:,.2f}"
            else:
                self.tcs_amt_lbl.value = "Not Appl."
            
            grand_total = sub_total + actual_tcs

            # Round UP only
            rounded_total = math.ceil(grand_total)
            diff = rounded_total - grand_total

            self.no_of_items_lbl.value = f"No. Of Items: {len(self.order_items)}"
            self.total_pcs.value     = f"Total Pcs: {int(total_pcs)}"
            self.total_boxes.value   = f"Total Boxes: {total_boxes:.1f}"
            self.total_units.value   = f"Total Units: {int(total_pcs)}"
            self.taxable_value.value = f"Taxable: ₹{final_taxable:,.2f}"
            self.gst_amount.value    = f"Total GST: ₹{actual_tax:,.2f}"
            self.round_off.value     = f"{diff:0.2f}"
            self.gross_amount.value  = f"Total: ₹{rounded_total:,.2f}"
            self.no_of_cases.value   = str(math.ceil(total_boxes))
            
            # Print for debug (visible in console)
            
            if self.page:
                self.update()
        except Exception as ex:
            print(f"Update Totals Error: {ex}")

    # ─────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────
    def save_order(self, e):
        if not self.party_dd.value or not self.order_items:
            self.page.snack_bar = ft.SnackBar(ft.Text("Select Party and add at least one item!"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()
            return
        if not self.tax_type_dd.value:
            self.page.snack_bar.content = ft.Text("Please select a Tax Type (GST/IGST) before saving!")
            self.page.snack_bar.bgcolor = ft.colors.RED_700
            self.page.snack_bar.open = True
            self.page.update()
            return

        try:
            order_val = self.order_no.value or get_next_doc_no("orders", "O", state.company_id, "order_no")
            
            def safe_float_label(ctrl, default=0):
                val = str(ctrl.value or "")
                if "₹" in val:
                    try:
                        # Extract the numeric part after ₹
                        return float(val.split("₹")[1].replace(",", ""))
                    except:
                        return default
                elif any(char.isdigit() for char in val):
                    try:
                        return float(''.join(c for c in val if c.isdigit() or c == '.'))
                    except:
                        return default
                return default

            # Calculate Total Tax for vat_cst_amount
            total_tax_amt = (
                safe_float_label(self.cgst_amt_lbl) + 
                safe_float_label(self.sgst_amt_lbl) + 
                safe_float_label(self.igst_amt_lbl) + 
                safe_float_label(self.cess_amt_lbl) + 
                safe_float_label(self.tcs_amt_lbl)
            )

            # Calculate Base Sum (Gross before footer discounts)
            base_sum = 0
            for item in self.order_items:
                meta  = self.all_items_metadata.get(str(item["item_id"]), {})
                inner = meta.get("pcs_per_inner_box",  1) or 1
                outer = meta.get("boxes_per_outer_box", 1) or 1
                is_box = self.qty_type.selected == {"box"}
                pcs   = item["qty"] * inner * outer if is_box else item["qty"]
                amount = pcs * item["rate"]
                disc   = amount * (item.get("disc_p", 0) / 100)
                base_sum += (amount - disc)

            header = {
                "company_id":     state.company_id,
                "order_no":       order_val,
                "order_date":     self.order_date.value,
                "party_id":       self.party_dd.value,
                "agent_id":       self.agent_dd.value,
                "transporter_id": self.transporter_dd.value,
                "price_list_id":  self.price_list_dd.value,
                "price_type":     self.price_type_dd.value,
                "destination":    self.destination.value,
                "order_by":       self.order_by.value,
                "order_thro":     self.order_thro.value,
                "party_order_no": self.party_order_no.value,
                "party_order_date": self.party_order_dt.value,
                "remarks":        self.remarks.value,
                "no_of_cases":    int(self.no_of_cases.value or 0),
                "documents_by":   self.docs_by.value,
                "total_pcs":      int(safe_float_label(self.total_pcs)),
                "total_boxes":    safe_float_label(self.total_boxes),
                
                # Discounts
                "td_percent":     float(self.trade_disc.value or 0),
                "td_amount":      safe_float_label(self.td_amt_lbl),
                "spd_percent":    float(self.scheme_disc.value or 0),
                "spd_amount":     safe_float_label(self.spd_amt_lbl),
                "festival_percent": float(self.fest_disc.value or 0),
                "festival_amount":  safe_float_label(self.fd_amt_lbl),
                "scd_percent":    float(self.spec_disc.value or 0),
                "scd_amount":     safe_float_label(self.scd_amt_lbl),
                "cd_percent":     float(self.cash_disc.value or 0),
                "cd_amount":      safe_float_label(self.cd_amt_lbl),
                
                # Tax (Note: We use vat_cst_amount for the total combined tax)
                "tax_type":       self.tax_type_dd.value,
                "tax_per":        float(self.gst_rate_tf.value or 0),
                "vat_cst_amount": total_tax_amt,
                "total_amount":   safe_float_label(self.taxable_value),
                "round_off":      float(self.round_off.value or 0),
                "net_amount":     safe_float_label(self.gross_amount),
                "no_of_items":    len(self.order_items),
                "status":         "Pending"
            }
            if self.current_edit_id:
                # Update existing
                order_id = self.current_edit_id
                update("orders", header, {"id": order_id})
                # Clear old items
                delete("order_items", {"order_id": order_id})
            else:
                # Insert new
                res = insert("orders", header)
                if not res:
                    raise Exception("Failed to save order header")
                order_id = res[0]["id"]

            # Calculate Footer Discount Multiplier
            footer_multiplier = 1.0
            for key in self._discount_order:
                meta = self.DISCOUNT_MAP.get(key)
                if meta:
                    d = float(meta["field"].value or 0)
                    footer_multiplier *= (1 - d / 100)

            for item in self.order_items:
                meta  = self.all_items_metadata.get(str(item["item_id"]), {})
                inner = meta.get("pcs_per_inner_box",  1) or 1
                outer = meta.get("boxes_per_outer_box", 1) or 1
                is_box = "box" in self.qty_type.selected
                pcs   = item["qty"] * inner * outer if is_box else item["qty"]
                boxes = item["qty"] if is_box else pcs / (inner * outer)
                
                # Combine row-level and footer discounts into a single Net Rate
                item_multiplier = (1 - item.get("disc_p", 0) / 100)
                net_multiplier = item_multiplier * footer_multiplier
                net_rate = item["rate"] * net_multiplier
                
                amount = pcs * net_rate
                
                insert("order_items", {
                    "order_id":        order_id,
                    "company_id":      state.company_id,
                    "item_id":         item["item_id"],
                    "item_name":       item.get("item_name"),
                    "size_value":      item["sizes_label"],
                    "rate":            round(item["rate"], 2), # Save Gross Rate from Order
                    "qty_pieces":      int(pcs),
                    "qty_boxes":       float(boxes),
                    "amount":          round(amount, 2), # Net Amount after all discounts
                    "discount_amount": round(pcs * item["rate"] * (1 - net_multiplier), 2),
                    "gross_amount":    round(pcs * item["rate"], 2),
                    "tax_percent":     float(self.gst_rate_tf.value or 0),
                })

            # Fetch the saved order to generate PDF
            saved_order = select("orders", {"id": order_id})
            if saved_order:
                order_data = saved_order[0]
                p_data = select("parties", {"id": order_data["party_id"]})
                if p_data:
                    order_data["party_name"] = p_data[0]["name"]
                
                if order_data.get("agent_id"):
                    a_data = select("agents", {"id": order_data["agent_id"]})
                    if a_data:
                        order_data["agent_name"] = a_data[0]["name"]
                
                if order_data.get("transporter_id"):
                    t_data = select("transporters", {"id": order_data["transporter_id"]})
                    if t_data:
                        order_data["transporter_name"] = t_data[0]["name"]
                # We need all items for PDF
                o_items = select("order_items", {"order_id": order_id})
                for o_it in o_items:
                    if not o_it.get("item_name"):
                        i_data = select("items", {"id": o_it["item_id"]})
                        o_it["item_name"] = i_data[0]["item_name"] if i_data else "Unknown"

                comp_data = select("companies", {"id": state.company_id})
                company = comp_data[0] if comp_data else {}
                pdf_path = pdf_engine.generate_order(order_data, o_items, company)
                print_pdf(pdf_path)

            self.page.snack_bar = ft.SnackBar(ft.Text("✅ Order Saved Successfully & PDF Generated!"), bgcolor="green")
            self.page.snack_bar.open = True
            self.clear_form(None)

        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    # ─────────────────────────────────────────────────────────
    # Clear
    # ─────────────────────────────────────────────────────────
    def clear_form(self, e=None):
        self.order_no.value = get_next_doc_no("orders", "O", state.company_id, "order_no")
        self.order_date.value = date.today().isoformat()
        self.party_dd.value = None
        self.agent_dd.value = None
        self.transporter_dd.value = None
        self.destination.value = ""
        self.order_by.value = ""
        self.party_order_no.value = ""
        self.party_order_dt.value = date.today().isoformat()
        self.remarks.value = ""
        self.no_of_cases.value = "1"
        self.qty_type.selected = {"pcs"}
        self.trade_disc.value = "0"
        self.scheme_disc.value = "0"
        self.fest_disc.value = "0"
        self.spec_disc.value = "0"
        self.cash_disc.value = "0"
        self.round_off.value = "0.00"
        self._discount_order = list(self.DEFAULT_DISCOUNT_ORDER)
        self._reorder_discount_fields()
        self.order_items = []
        self.items_col.controls = []
        self.current_edit_id = None
        self.update_totals()
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # History & Printing
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        orders = select("orders", {"company_id": state.company_id})
        # Sort by created_at DESC (latest first)
        orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        parties = select("parties", {"company_id": state.company_id})
        party_map = {str(p["id"]): p["name"] for p in parties}
        
        lv = ft.ListView(expand=1, spacing=10, padding=20)
        for ord in orders:
            p_name = party_map.get(str(ord.get("party_id")), "Unknown")
            ord["party_name"] = p_name
            
            lv.controls.append(
                ft.Container(
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{ord.get('order_no')}", weight="bold", size=14),
                            ft.Row([
                                ft.Icon(ft.icons.CALENDAR_TODAY, size=12, color=ft.colors.BLUE_GREY_400),
                                ft.Text(f"{ord.get('order_date')}", size=11, color=ft.colors.BLUE_GREY_600),
                                ft.VerticalDivider(width=10),
                                ft.Icon(ft.icons.ACCESS_TIME, size=12, color=ft.colors.BLUE_GREY_400),
                                ft.Text(self._format_timestamp(ord.get('created_at')), size=11, color=ft.colors.BLUE_GREY_600),
                            ], spacing=5),
                            ft.Text(p_name, size=13, weight="w500", color=AppColors.PRIMARY),
                        ], expand=True, spacing=4),
                        ft.Column([
                            ft.Text(f"Pcs: {int(ord.get('total_pcs', 0))}", size=12, weight="bold"),
                            ft.Text(f"₹ {float(ord.get('net_amount', 0)):,.2f}", size=16, weight="bold", color=ft.colors.GREEN_700),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                        ft.Row([
                            ft.IconButton(ft.icons.EDIT_OUTLINED, tooltip="Edit Order", icon_color=AppColors.PRIMARY, 
                                          on_click=lambda e, o=ord: self.load_order_for_edit(o, dlg)),
                            ft.IconButton(ft.icons.PRINT, tooltip="Print Order", icon_color=ft.colors.BLUE_700, 
                                          on_click=lambda e, o=ord: self.print_history_order(o)),
                            ft.IconButton(ft.icons.DELETE_OUTLINE, tooltip="Delete Order", icon_color="red",
                                          on_click=lambda e, o=ord: self.delete_order_from_history(o, dlg))
                        ])
                    ])
                )
            )
            
        dlg = ft.AlertDialog(
            title=ft.Text("Recent Orders"),
            content=ft.Container(width=600, height=400, content=lv),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def load_order_for_edit(self, order, dlg):
        """Loads a past order into the main form for editing."""
        try:
            self._close_dialog(dlg)
            self.clear_form()
            
            self.current_edit_id = order["id"]
            self.order_no.value   = order.get("order_no", "")
            self.order_date.value = order.get("order_date", "")
            self.party_dd.value   = str(order.get("party_id"))
            self.agent_dd.value   = str(order.get("agent_id")) if order.get("agent_id") else None
            self.transporter_dd.value = str(order.get("transporter_id")) if order.get("transporter_id") else None
            self.price_list_dd.value  = str(order.get("price_list_id")) if order.get("price_list_id") else None
            self.price_type_dd.value  = order.get("price_type", "Wholesale")
            self.destination.value    = order.get("destination", "")
            self.order_by.value       = order.get("order_by", "")
            self.order_thro.value     = order.get("order_thro", "DIRECT")
            self.party_order_no.value = order.get("party_order_no", "")
            self.party_order_dt.value = order.get("party_order_date", "")
            self.remarks.value        = order.get("remarks", "")
            self.no_of_cases.value    = str(order.get("no_of_cases", 1))
            
            # Tax & Discounts
            self.tax_type_dd.value = order.get("tax_type", "GST")
            self.gst_rate_tf.value  = str(order.get("tax_per", 5))
            
            self.trade_disc.value  = str(order.get("td_percent", 0))
            self.scheme_disc.value = str(order.get("spd_percent", 0))
            self.fest_disc.value   = str(order.get("festival_percent", 0))
            self.spec_disc.value   = str(order.get("scd_percent", 0))
            self.cash_disc.value   = str(order.get("cd_percent", 0))
            
            # Load items
            db_items = select("order_items", {"order_id": order["id"]})
            
            # Group items by (item_id, rate) to match the UI row structure
            # (In Tirupur ERP, multiple sizes at same rate are grouped in one row)
            item_groups = {}
            for it in db_items:
                # We need to reconstruct the item_name and sizes_label
                meta = self.all_items_metadata.get(str(it["item_id"]), {})
                key = (str(it["item_id"]), float(it["rate"]))
                if key not in item_groups:
                    item_groups[key] = {
                        "item_id": it["item_id"],
                        "item_name": meta.get("item_name", "Unknown"),
                        "rate": float(it["rate"]),
                        "qty": 0,
                        "disc_p": 0, # Assume uniform discount for simplicity, or fetch from first item
                        "sizes": []
                    }
                item_groups[key]["qty"] += int(it["qty_pieces"])
                item_groups[key]["sizes"].append(it["size_value"])
            
            for g in item_groups.values():
                g["sizes_label"] = ", ".join(g["sizes"])
                self.order_items.append(g)

            self.rebuild_grid()
            self.on_calc_change() # Force UI to split CGST/SGST
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Loaded Order: {self.order_no.value}"), bgcolor=AppColors.PRIMARY)
            self.page.snack_bar.open = True
            self.page.update()
        except Exception as ex:
            print(f"Edit Load Error: {ex}")
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Failed to load order: {ex}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    def _format_timestamp(self, ts):
        if not ts: return "-"
        try:
            # Assumes ISO format from Postgres
            from datetime import datetime
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%b %d, %Y %I:%M %p")
        except:
            return str(ts)[:16]

    def delete_order_from_history(self, order, dlg):
        """Deletes an order and its items from the database, checking for dependencies."""
        def confirm_delete(e):
            try:
                order_id = order["id"]
                order_no = order.get("order_no", "")

                # Check full downstream chain
                linked_slips = select("packing_slip_items", {"order_id": order_id})
                if linked_slips:
                    confirm_dlg.open = False
                    self.page.update()
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text("Cannot delete: Order is linked to Packing Slips. Delete the slips first."),
                        bgcolor="orange"
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                # Also check if order referenced in packing_slips header
                linked_ps = select("packing_slips", {"order_id": order_id})
                if linked_ps:
                    confirm_dlg.open = False
                    self.page.update()
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text(f"Cannot delete: Order has {len(linked_ps)} Packing Slip(s). Delete them first."),
                        bgcolor="orange"
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                # Safe to delete — clean up everything
                delete("order_items", {"order_id": order_id})
                delete("orders", {"id": order_id})

                # Clean up ledger & stock entries tied to this order
                try:
                    delete("ledger_entries", {"company_id": state.company_id, "ref_type": "Sales Order", "ref_id": order_no})
                    delete("stock_ledger",  {"company_id": state.company_id, "ref_type": "Sales Order", "ref_id": order_no})
                except Exception:
                    pass

                confirm_dlg.open = False
                dlg.open = False
                self.page.update()

                self.page.snack_bar = ft.SnackBar(ft.Text(f"Order {order_no} deleted successfully"), bgcolor="green")
                self.page.snack_bar.open = True
                self.page.update()

                # Refresh history modal
                self.show_history_modal(None)
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Delete Error: {ex}"), bgcolor="red")
                self.page.snack_bar.open = True
                self.page.update()

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete order {order.get('order_no')}? This cannot be undone."),
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

    def print_history_order(self, order):
        try:
            items = select("order_items", {"order_id": order["id"]})
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}

            if order.get("party_id"):
                p_data = select("parties", {"id": order["party_id"]})
                if p_data: order["party_name"] = p_data[0]["name"]
            if order.get("agent_id"):
                a_data = select("agents", {"id": order["agent_id"]})
                if a_data: order["agent_name"] = a_data[0]["name"]
            if order.get("transporter_id"):
                t_data = select("transporters", {"id": order["transporter_id"]})
                if t_data: order["transporter_name"] = t_data[0]["name"]

            pdf_path = pdf_engine.generate_order(order, items, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error printing: {ex}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()


# =========================================================
# SALES SCREEN - Tab container for all Sales transactions
# =========================================================
from screens.packing_slip import PackingSlipTab
from screens.transport_invoice import TransportInvoiceTab
from screens.sales_invoice import SalesInvoiceTab
from screens.vouchers import ChequeTab


class SalesScreen(ft.Column):
    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        self.order_tab     = OrderEntryTab()
        self.packing_tab   = PackingSlipTab()
        self.transport_tab = TransportInvoiceTab()
        self.invoice_tab   = SalesInvoiceTab()
        self.cheque_tab    = ChequeTab()

        self.tab_bar = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            expand=True,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            indicator_color=AppColors.PRIMARY,
            tabs=[
                ft.Tab(text="Order Entry",       content=self.order_tab),
                ft.Tab(text="Packing Slips",     content=self.packing_tab),
                ft.Tab(text="Transport Invoice", content=self.transport_tab),
                ft.Tab(text="Sales Invoice",     content=self.invoice_tab),
                ft.Tab(text="Cheque Entry",      content=self.cheque_tab),
            ],
        )

        self.controls = [self.tab_bar]
