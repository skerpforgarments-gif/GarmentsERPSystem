import flet as ft
import uuid
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert
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

        # Party-level GST rate (set when party is chosen)
        self._party_gst_rate = 5.0
        self._party_tax_type = "GST"

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
        
        self.taxable_value = ft.Text("Taxable: ₹0.00",   size=14, weight="bold")
        self.gst_amount    = ft.Text("GST (5%): ₹0.00",  size=13, color=AppColors.TEXT_SUB)
        self.round_off     = ft.TextField(label="Round Off", value="0.00", width=100, on_change=self.on_calc_change, **S)
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
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
            content=ft.Row([
                ft.Text("IC CODE",    width=80,  size=11, weight="bold"),
                ft.Text("DESCRIPTION", width=200, size=11, weight="bold"),
                ft.Text("TOTAL PCS",  width=90,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("TOTAL BOXES", width=95,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("TOTAL UNITS", width=95,  size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("ACTIONS",    expand=True, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
            ]),
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
                    ft.Row([
                        ft.Column([self.trade_disc, self.td_amt_lbl], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        ft.Column([self.scheme_disc, self.spd_amt_lbl], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        ft.Column([self.fest_disc, self.fd_amt_lbl], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        ft.Column([self.spec_disc, self.scd_amt_lbl], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        ft.Column([self.cash_disc, self.cd_amt_lbl], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    ], spacing=15),
                ]),
                ft.Divider(height=1, color="#E2E8F0"),
                # Row 2: Final Totals and Actions
                ft.Row([
                    ft.Column([self.taxable_value, self.gst_amount], spacing=2),
                    ft.Container(expand=True),
                    self.round_off,
                    ft.Container(width=20),
                    self.gross_amount,
                    ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.load_metadata(), tooltip="Refresh Metadata"),
                    ft.IconButton(ft.icons.CLEAR_ALL, on_click=self.clear_form, icon_color="orange"),
                    ft.ElevatedButton(
                        "Confirm & Save Order",
                        icon=ft.icons.SAVE_ALT,
                        on_click=self.save_order,
                        height=50,
                        style=AppStyles.primary_button_style(),
                    ),
                ]),
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
        items = select("items", {"company_id": state.company_id})
        self.all_items_metadata = {str(i["id"]): i for i in items}

        self.matrix_modal = SizeMatrixModal(on_submit=self.add_matrix_results)
        if self.page and self.matrix_modal not in self.page.overlay:
            self.page.overlay.append(self.matrix_modal)
            self.page.update()
        self.matrix_modal.load_items(items)

        parties      = select("parties",      {"company_id": state.company_id})
        transporters = select("transporters", {"company_id": state.company_id})
        price_lists  = select("price_lists",  {"company_id": state.company_id})
        agents       = select("agents",       {"company_id": state.company_id})

        self.party_dd.options       = [ft.dropdown.Option(key=str(p["id"]), text=p["name"])      for p in parties]
        self.transporter_dd.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"])      for t in transporters]
        self.price_list_dd.options  = [ft.dropdown.Option(key=str(p["id"]), text=p["list_name"]) for p in price_lists]
        self.agent_dd.options       = [ft.dropdown.Option(key=str(a["id"]), text=a["name"])      for a in agents]

        if not self.order_no.value:
            self.order_no.value = f"ORD-{uuid.uuid4().hex[:6].upper()}"

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
            # Auto-fill all 5 discount tiers from Party Master
            self.trade_disc.value  = str(p.get("discount_trade",    0))
            self.scheme_disc.value = str(p.get("discount_scheme",   0))
            self.fest_disc.value   = str(p.get("discount_festival", 0))
            self.spec_disc.value   = str(p.get("discount_scd",      0))  # Special Cash Discount
            self.cash_disc.value   = str(p.get("discount_cd",       0))  # Cash Discount
            # Store party-level GST for totals calculation
            self._party_gst_rate = float(p.get("gst_percent", 5) or 5)
            self._party_tax_type = p.get("tax_type", "GST") or "GST"
            self.update_totals()
            self.update()

    def on_calc_change(self, e=None):
        self.update_totals()
        self.update()

    def on_qty_type_change(self, e):
        self.rebuild_grid()

    def open_size_matrix(self, e):
        if not self.price_list_dd.value:
            self.page.snack_bar = ft.SnackBar(ft.Text("Please select a Price List first!"), bgcolor="orange")
            self.page.snack_bar.open = True
            self.page.update()
            return
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
        pcs   = item["qty"] * inner * outer if is_box else item["qty"]
        boxes = item["qty"] if is_box else pcs / (inner * outer)
        amount  = pcs * item["rate"]
        disc    = amount * (item.get("disc_p", 0) / 100)
        taxable = amount - disc
        tax_rate = self._party_gst_rate
        tax_amt  = taxable * (tax_rate / 100)
        gross    = taxable + tax_amt

        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
            content=ft.Row([
                ft.Text(item["item_name"],        width=200, size=13, weight="w500"),
                ft.Text(item["sizes_label"],      width=110, size=11, color=AppColors.PRIMARY, italic=True),
                ft.Text(str(item["qty"]),         width=50,  size=13, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text(str(int(pcs)),            width=50,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"{boxes:.1f}",           width=55,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"₹{item['rate']}",       width=70,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"{item['disc_p']:.1f}%", width=55,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"₹{taxable:,.2f}",       width=80,  size=13, text_align=ft.TextAlign.RIGHT),
                ft.Text(f"{tax_rate:.0f}%",       width=55,  size=13, text_align=ft.TextAlign.RIGHT, color=AppColors.TEXT_SUB),
                ft.Text(f"₹{gross:,.2f}", expand=True, size=13, weight="bold",
                        text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY),
            ]),
        )

    def rebuild_grid(self):
        self.items_col.controls = [self._make_row(item) for item in self.order_items]
        self.update_totals()
        if self.page:
            self.items_col.update()

    # ─────────────────────────────────────────────────────────
    # Totals
    # ─────────────────────────────────────────────────────────
    def update_totals(self):
        total_pcs = total_boxes = gross_sum = 0
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
            gross_sum   += (amount - disc)

        try:
            val = gross_sum
            for f in [self.trade_disc, self.scheme_disc, self.fest_disc, self.spec_disc, self.cash_disc]:
                d = float(f.value or 0)
                val -= val * (d / 100)
            gst_rate = self._party_gst_rate
            gst      = val * (gst_rate / 100)
            tax_label = self._party_tax_type
            self.no_of_items_lbl.value = f"No. Of Items: {len(self.order_items)}"
            self.total_pcs.value     = f"Total Pcs: {int(total_pcs)}"
            self.total_boxes.value   = f"Total Boxes: {total_boxes:.1f}"
            self.total_units.value   = f"Total Units: {int(total_pcs)}"  # In Order Entry, Units = Pcs usually
            self.taxable_value.value = f"Taxable: ₹{val:,.2f}"
            self.gst_amount.value    = f"{tax_label} ({gst_rate:.0f}%): ₹{gst:,.2f}"
            self.gross_amount.value  = f"Total: ₹{val + gst:,.2f}"
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────
    def save_order(self, e):
        if not self.party_dd.value or not self.order_items:
            self.page.snack_bar = ft.SnackBar(ft.Text("Select Party and add at least one item!"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()
            return
        try:
            order_val = self.order_no.value or f"ORD-{uuid.uuid4().hex[:6].upper()}"
            
            def safe_split_val(ctrl, default=0):
                val = str(ctrl.value or "")
                if ": " in val:
                    try:
                        return float(val.split(": ")[1].replace("₹","").replace(",",""))
                    except:
                        return default
                return default

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
                "total_pcs":      int(safe_split_val(self.total_pcs)),
                "total_boxes":    safe_split_val(self.total_boxes),
                "td_percent":     float(self.trade_disc.value or 0),
                "spd_percent":    float(self.scheme_disc.value or 0),
                "festival_percent": float(self.fest_disc.value or 0),
                "scd_percent":    float(self.spec_disc.value or 0),
                "cd_percent":     float(self.cash_disc.value or 0),
                "tax_type":       self._party_tax_type,
                "tax_per":        self._party_gst_rate,
                "total_amount":   safe_split_val(self.taxable_value),
                "round_off":      float(self.round_off.value or 0),
                "net_amount":     safe_split_val(self.gross_amount),
                "status":         "Pending"
            }
            res = insert("orders", header)
            if not res:
                raise Exception("Failed to save order header")
            order_id = res[0]["id"]

            for item in self.order_items:
                meta  = self.all_items_metadata.get(str(item["item_id"]), {})
                inner = meta.get("pcs_per_inner_box",  1) or 1
                outer = meta.get("boxes_per_outer_box", 1) or 1
                is_box = "box" in self.qty_type.selected
                pcs   = item["qty"] * inner * outer if is_box else item["qty"]
                boxes = item["qty"] if is_box else pcs / (inner * outer)
                amount = pcs * item["rate"]
                disc   = amount * (item.get("disc_p", 0) / 100)
                insert("order_items", {
                    "order_id":        order_id,
                    "company_id":      state.company_id,
                    "item_id":         item["item_id"],
                    "size_value":      item["sizes_label"],
                    "rate":            item["rate"],
                    "qty_pieces":      int(pcs),
                    "qty_boxes":       float(boxes),
                    "amount":          amount,
                    "discount_amount": disc,
                    "gross_amount":    amount - disc,
                    "tax_percent":     5.0,
                })

            # Fetch the saved order to generate PDF
            saved_order = select("orders", {"id": order_id})
            if saved_order:
                order_data = saved_order[0]
                p_data = select("parties", {"id": order_data["party_id"]})
                if p_data:
                    order_data["party_name"] = p_data[0]["name"]
                
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
        self.order_no.value = f"ORD-{uuid.uuid4().hex[:6].upper()}"
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
        self.trade_disc.value = "0"
        self.scheme_disc.value = "0"
        self.fest_disc.value = "0"
        self.spec_disc.value = "0"
        self.cash_disc.value = "0"
        self.round_off.value = "0.00"
        self.order_items = []
        self.items_col.controls = []
        self.on_calc_change(None)
        if self.page: self.update()

    # ─────────────────────────────────────────────────────────
    # History & Printing
    # ─────────────────────────────────────────────────────────
    def show_history_modal(self, e):
        orders = select("orders", {"company_id": state.company_id})
        orders.sort(key=lambda x: x.get("order_date", ""), reverse=True)
        
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
                            ft.Text(f"{ord.get('order_no')}  |  {ord.get('order_date')}", weight="bold", size=14),
                            ft.Text(p_name, size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"Pcs: {ord.get('total_pcs', 0)}", size=12),
                        ft.Text(f"₹ {float(ord.get('total_amount', 0)):,.2f}", size=14, weight="bold", color=AppColors.PRIMARY),
                        ft.IconButton(ft.icons.PRINT, tooltip="Print Order", icon_color=ft.colors.BLUE_700, 
                                      on_click=lambda e, o=ord: self.print_history_order(o))
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

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def print_history_order(self, order):
        try:
            items = select("order_items", {"order_id": order["id"]})
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
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
