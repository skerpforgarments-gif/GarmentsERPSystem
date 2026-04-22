import flet as ft
from core.theme import AppColors, AppStyles


from core.state import state
from database.db import select, insert, delete, update
from components.table import TableBuilder
from components.form import FormBuilder
from components.item_master_form import ItemMasterForm
from components.price_list_form import PriceListForm


# =========================================================
# INLINE PARTY MASTER FORM
# =========================================================
class PartyMasterForm(ft.Container):
    def __init__(self, on_submit=None):
        super().__init__()
        self.expand = True
        self.padding = 8
        self.on_submit = on_submit
        
        # Unified Styling
        self.style_args = AppStyles.get_input_style()

        # --- Basic Info ---
        self.name = ft.TextField(label="Party Name *", width=280, **self.style_args)
        self.addr1 = ft.TextField(label="Address Line 1", width=280, **self.style_args)
        self.addr2 = ft.TextField(label="Address Line 2", width=280, **self.style_args)
        self.addr3 = ft.TextField(label="Address Line 3", width=280, **self.style_args)
        self.city = ft.TextField(label="City", width=160, **self.style_args)
        self.district = ft.TextField(label="District", width=160, **self.style_args)
        self.state_field = ft.TextField(label="State", width=160, **self.style_args)
        self.pincode = ft.TextField(label="Pincode", width=120, **self.style_args)
        self.code = ft.TextField(label="Code", width=100, **self.style_args)
        self.phone = ft.TextField(label="Phone", width=160, **self.style_args)
        self.mobile = ft.TextField(label="Mobile", width=160, **self.style_args)
        self.fax = ft.TextField(label="Fax", width=120, **self.style_args)
        self.email = ft.TextField(label="Email", width=220, **self.style_args)

        # --- Tax Info ---
        self.gstin = ft.TextField(label="GSTIN", width=200, **self.style_args)
        self.cst_no = ft.TextField(label="CST No", width=160, **self.style_args)
        self.pan_no = ft.TextField(label="PAN No", width=160, **self.style_args)

        # --- Linked Masters ---
        self.agent_id = ft.Dropdown(label="Select Agent", width=200, **self.style_args)
        self.transporter_id = ft.Dropdown(label="Select Transporter", width=200, **self.style_args)
        self.destination = ft.TextField(label="Destination", width=160, **self.style_args)
        self.courier_name = ft.TextField(label="Courier Name", width=200, **self.style_args)
        self.reference = ft.TextField(label="Reference", width=160, **self.style_args)

        # --- Documents & Order ---
        self.documents_thro = ft.Dropdown(
            label="Documents Thro'", width=160, value="Direct", **self.style_args,
            options=[ft.dropdown.Option("Direct"), ft.dropdown.Option("Bank")]
        )
        self.order_thro = ft.Dropdown(
            label="Order Thro'", width=160, value="DIRECT", **self.style_args,
            options=[ft.dropdown.Option("DIRECT"), ft.dropdown.Option("AGENT")]
        )

        # --- Financial Terms ---
        self.opening_balance = ft.TextField(label="Opening Balance", width=150, value="0",
                                             keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.opn_bal_type = ft.Dropdown(
            label="Type", width=120, value="DEBIT", **self.style_args,
            options=[ft.dropdown.Option("DEBIT"), ft.dropdown.Option("CREDIT")]
        )
        self.for_allowed = ft.Dropdown(
            label="F.O.R Allowed", width=140, value="Yes", **self.style_args,
            options=[ft.dropdown.Option("Yes"), ft.dropdown.Option("No")]
        )
        self.credit_days = ft.TextField(label="Credit Days", width=120, value="0",
                                         keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.credit_limit = ft.TextField(label="Credit Limit Rs", width=150, value="0",
                                          keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.price_type = ft.Dropdown(
            label="Price Type", width=140, value="Wholesale", **self.style_args,
            options=[
                ft.dropdown.Option("Wholesale"),
                ft.dropdown.Option("Retail"),
                ft.dropdown.Option("MRP")
            ]
        )
        self.price_list_id = ft.Dropdown(label="Select Price List", width=200, **self.style_args)

        # --- Tax Settings ---
        self.tax_type = ft.Dropdown(
            label="Tax Type", width=140, value="GST", **self.style_args,
            options=[ft.dropdown.Option("GST"), ft.dropdown.Option("IGST"), ft.dropdown.Option("TCS")]
        )
        self.gst_percent = ft.TextField(label="GST %", width=100, value="0",
                                         keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.igst_percent = ft.TextField(label="IGST %", width=100, value="0",
                                          keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.tcs_applicable = ft.Checkbox(label="TCS", value=False, check_color=AppColors.PRIMARY)

        # --- Discounts ---
        self.disc_trade = ft.TextField(label="TD %", width=90, value="0",
                                         keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.disc_scheme = ft.TextField(label="SPD %", width=90, value="0",
                                          keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.disc_scd = ft.TextField(label="SCD %", width=90, value="0",
                                       keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.disc_cd = ft.TextField(label="CD %", width=90, value="0",
                                     keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)
        self.disc_festival = ft.TextField(label="Festival %", width=90, value="0",
                                           keyboard_type=ft.KeyboardType.NUMBER, **self.style_args)

        # --- Bank Details ---
        self.bank_name = ft.TextField(label="Bank Name", width=220, **self.style_args)
        self.bank_acc = ft.TextField(label="Account No", width=220, **self.style_args)
        self.bank_ifsc = ft.TextField(label="IFSC Code", width=140, **self.style_args)

        # --- Status ---
        self.remarks = ft.TextField(label="Remarks", width=300, **self.style_args)
        
        self.status_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="Approved", label="Approved"),
                ft.Radio(value="Blocked", label="Blocked")
            ], spacing=20),
            value="Approved"
        )

        # --- Action Buttons ---
        save_btn = ft.ElevatedButton(
            "Save Party", 
            icon=ft.icons.SAVE, 
            on_click=self._submit,
            style=AppStyles.primary_button_style(),
            height=45
        )
        clear_btn = ft.TextButton(
            "Clear", 
            icon=ft.icons.REFRESH, 
            on_click=self.clear,
            style=AppStyles.secondary_button_style()
        )

        # --- Layout ---
        def section(title, controls):
            return ft.Container(
                content=ft.Column([
                    ft.Text(title.upper(), weight="bold", size=10, color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Divider(height=1, color="#F1F5F9"),
                    *controls
                ], spacing=15),
                border_radius=AppStyles.RADIUS,
                bgcolor="#FFFFFF",
                padding=20,
                border=ft.border.all(1, "#F1F5F9"),
                margin=ft.margin.only(bottom=20)
            )

        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            controls=[
                section("Basic Information", [
                    ft.Row([self.name, self.code], spacing=10, wrap=True),
                    ft.Row([self.addr1, self.addr2], spacing=10, wrap=True),
                    ft.Row([self.addr3], spacing=10, wrap=True),
                    ft.Row([self.city, self.district, self.state_field, self.pincode], spacing=10, wrap=True),
                    ft.Row([self.phone, self.mobile, self.fax, self.email], spacing=10, wrap=True),
                ]),
                section("Tax Information", [
                    ft.Row([self.gstin, self.cst_no, self.pan_no], spacing=10, wrap=True),
                ]),
                section("Logistics", [
                    ft.Row([self.agent_id, self.transporter_id, self.destination, self.courier_name], spacing=10, wrap=True),
                    ft.Row([self.documents_thro, self.order_thro, self.reference], spacing=10, wrap=True),
                ]),
                section("Financial Terms", [
                    ft.Row([self.opening_balance, self.opn_bal_type, self.for_allowed], spacing=10, wrap=True),
                    ft.Row([self.credit_days, self.credit_limit, self.price_list_id, self.price_type], spacing=10, wrap=True),
                ]),
                section("Tax Settings", [
                    ft.Row([self.tax_type, self.gst_percent, self.igst_percent, self.tcs_applicable], spacing=10, wrap=True),
                ]),
                section("Discount Structure", [
                    ft.Row([self.disc_trade, self.disc_scheme, self.disc_scd, self.disc_cd, self.disc_festival], spacing=10, wrap=True),
                ]),
                section("Bank Details", [
                    ft.Row([self.bank_name, self.bank_acc, self.bank_ifsc], spacing=10, wrap=True),
                ]),
                section("Status & Remarks", [
                    ft.Row([self.remarks, self.status_radio], spacing=25, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ]),
                ft.Row([save_btn, clear_btn], spacing=12, wrap=True),
            ]
        )

    def get_values(self):
        return {
            "name": self.name.value or "",
            "address_line1": self.addr1.value or "",
            "address_line2": self.addr2.value or "",
            "address_line3": self.addr3.value or "",
            "city": self.city.value or "",
            "district": self.district.value or "",
            "state": self.state_field.value or "",
            "pincode": self.pincode.value or "",
            "code": self.code.value or "",
            "phone": self.phone.value or "",
            "mobile": self.mobile.value or "",
            "fax": self.fax.value or "",
            "email": self.email.value or "",
            "gstin": self.gstin.value or "",
            "cst_no": self.cst_no.value or "",
            "pan_no": self.pan_no.value or "",
            "destination": self.destination.value or "",
            "courier_name": self.courier_name.value or "",
            "reference": self.reference.value or "",
            "agent_id": self.agent_id.value,
            "transporter_id": self.transporter_id.value,
            "price_list_id": self.price_list_id.value,
            "documents_thro": self.documents_thro.value or "Direct",
            "order_thro": self.order_thro.value or "DIRECT",
            "opening_balance": float(self.opening_balance.value or 0),
            "opn_bal_type": self.opn_bal_type.value or "DEBIT",
            "for_allowed": self.for_allowed.value == "Yes",
            "credit_days": int(self.credit_days.value or 0),
            "credit_limit": float(self.credit_limit.value or 0),
            "price_type": self.price_type.value or "Wholesale",
            "tax_type": self.tax_type.value or "GST",
            "gst_percent": float(self.gst_percent.value or 0),
            "igst_percent": float(self.igst_percent.value or 0),
            "tcs_applicable": self.tcs_applicable.value,
            "discount_trade": float(self.disc_trade.value or 0),
            "discount_scheme": float(self.disc_scheme.value or 0),
            "discount_scd": float(self.disc_scd.value or 0),
            "discount_cd": float(self.disc_cd.value or 0),
            "discount_festival": float(self.disc_festival.value or 0),
            "bank_name": self.bank_name.value or "",
            "bank_account_no": self.bank_acc.value or "",
            "bank_ifsc": self.bank_ifsc.value or "",
            "remarks": self.remarks.value or "",
            "is_approved": self.status_radio.value == "Approved",
            "is_blocked": self.status_radio.value == "Blocked",
        }

    def load_metadata(self, agents, transporters, price_lists):
        self.agent_id.options = [ft.dropdown.Option(key=str(a["id"]), text=a["name"]) for a in agents]
        self.transporter_id.options = [ft.dropdown.Option(key=str(t["id"]), text=t["name"]) for t in transporters]
        self.price_list_id.options = [ft.dropdown.Option(key=str(p["id"]), text=p["list_name"]) for p in price_lists]
        try:
            self.update()
        except:
            pass

    def set_values(self, data: dict):
        self.name.value = data.get("name", "")
        self.addr1.value = data.get("address_line1", "")
        self.addr2.value = data.get("address_line2", "")
        self.addr3.value = data.get("address_line3", "")
        self.city.value = data.get("city", "")
        self.district.value = data.get("district", "")
        self.state_field.value = data.get("state", "")
        self.pincode.value = data.get("pincode", "")
        self.code.value = data.get("code", "")
        self.phone.value = data.get("phone", "")
        self.mobile.value = data.get("mobile", "")
        self.fax.value = data.get("fax", "")
        self.email.value = data.get("email", "")
        self.gstin.value = data.get("gstin", "")
        self.cst_no.value = data.get("cst_no", "")
        self.pan_no.value = data.get("pan_no", "")
        self.destination.value = data.get("destination", "")
        self.courier_name.value = data.get("courier_name", "")
        self.reference.value = data.get("reference", "")
        
        if data.get("agent_id"):
            self.agent_id.value = str(data.get("agent_id"))
        if data.get("transporter_id"):
            self.transporter_id.value = str(data.get("transporter_id"))
        if data.get("price_list_id"):
            self.price_list_id.value = str(data.get("price_list_id"))
            
        self.documents_thro.value = data.get("documents_thro", "Direct")
        self.order_thro.value = data.get("order_thro", "DIRECT")
        self.opening_balance.value = str(data.get("opening_balance", 0))
        self.opn_bal_type.value = data.get("opn_bal_type", "DEBIT")
        self.for_allowed.value = "Yes" if data.get("for_allowed", True) else "No"
        self.credit_days.value = str(data.get("credit_days", 0))
        self.credit_limit.value = str(data.get("credit_limit", 0))
        self.price_type.value = data.get("price_type", "Wholesale")
        self.tax_type.value = data.get("tax_type", "GST")
        self.gst_percent.value = str(data.get("gst_percent", 0))
        self.igst_percent.value = str(data.get("igst_percent", 0))
        self.tcs_applicable.value = data.get("tcs_applicable", False)
        self.disc_trade.value = str(data.get("discount_trade", 0))
        self.disc_scheme.value = str(data.get("discount_scheme", 0))
        self.disc_scd.value = str(data.get("discount_scd", 0))
        self.disc_cd.value = str(data.get("discount_cd", 0))
        self.disc_festival.value = str(data.get("discount_festival", 0))
        self.bank_name.value = data.get("bank_name", "")
        self.bank_acc.value = data.get("bank_account_no", "")
        self.bank_ifsc.value = data.get("bank_ifsc", "")
        self.remarks.value = data.get("remarks", "")
        self.status_radio.value = "Blocked" if data.get("is_blocked", False) else "Approved"
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def clear(self, e=None):
        self.set_values({"is_approved": True, "is_blocked": False})

    def _submit(self, e):
        if not self.name.value:
            self.name.error_text = "Required"
            try:
                self.update()
            except Exception:
                pass
            return
        self.name.error_text = None
        if self.on_submit:
            self.on_submit(self.get_values())


# =========================================================
# MASTERS SCREEN (Full Tabbed Layout)
# =========================================================
class MastersScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 20
        self.edit_id = None
        self.current_tab = 0

        self.form_area = ft.Container()
        self.table_area = ft.Container(expand=True)

        # Modal Holder
        self.modal = ft.AlertDialog(
            modal=False,  # Allow clicking outside to close
            title=ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.EDIT_NOTE, color=AppColors.PRIMARY),
                    ft.Text("ENTRY MANAGEMENT", weight="bold", size=16),
                ], spacing=10),
                ft.IconButton(ft.icons.CLOSE, on_click=lambda _: self.close_modal())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            actions_alignment=ft.MainAxisAlignment.END,
            content=ft.Container(self.form_area, width=700, height=600)
        )

        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self.on_tab_change,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            divider_color="#F0F0F0",
            tabs=[
                ft.Tab(text="Items"),
                ft.Tab(text="Price Lists"),
                ft.Tab(text="Parties"),
                ft.Tab(text="Agents"),
                ft.Tab(text="Transporters"),
                ft.Tab(text="Banks"),
                ft.Tab(text="Taxes"),
                ft.Tab(text="Staff"),
                ft.Tab(text="Expense Ledger"),
                ft.Tab(text="General Items"),
            ]
        )

        # --- Top Button Bar ---
        self.add_entry_btn = ft.ElevatedButton(
            "Add Entry", 
            icon=ft.icons.ADD_ROUNDED,
            on_click=self.on_add_entry,
            style=ft.ButtonStyle(
                color=ft.colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=25, vertical=15)
            )
        )

        self.content = ft.Column(
            controls=[
                ft.Row([
                    ft.Column([
                        ft.Text("Master Data Management", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                        ft.Text("Define and manage your global infrastructure records.", size=AppStyles.BODY_SIZE, color=AppColors.TEXT_SUB),
                    ]),
                    self.add_entry_btn
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.tabs,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                
                # Full width Table
                self.table_area
            ],
            expand=True
        )

    def did_mount(self):
        if not self.page:
            return
        if self.modal not in self.page.overlay:
            self.page.overlay.append(self.modal)
            self.page.update()
        self.load_tab(0)

    def on_tab_change(self, e):
        self.current_tab = self.tabs.selected_index
        self.edit_id = None
        self.load_tab(self.current_tab)

    def on_add_entry(self, e):
        self.edit_id = None
        self.open_modal()  # Open first to attach to page
        if hasattr(self.form, "clear"):
            self.form.clear()

    def open_modal(self):
        self.modal.open = True
        if self.page:
            self.page.update()

    def close_modal(self):
        self.modal.open = False
        if self.page:
            self.page.update()

    def load_tab(self, idx):
        if not state.company_id:
            return

        loaders = [
            self.load_items, self.load_price_lists, self.load_parties,
            self.load_agents, self.load_transporters, self.load_banks,
            self.load_taxes, self.load_staff, self.load_expense_ledgers,
            self.load_general_items,
        ]
        if idx < len(loaders):
            loaders[idx]()

    def _refresh(self):
        if self.page:
            try:
                self.update()
            except Exception:
                pass

    def _confirm_delete(self, message, on_confirm):
        def handle_confirm(e):
            on_confirm()
            self.page.dialog.open = False
            self.page.update()

        self.page.dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.ORANGE), ft.Text("Confirm Delete")], spacing=10),
            content=ft.Text(message, size=14),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("Delete Permanently", on_click=handle_confirm, bgcolor=ft.colors.RED_400, color=ft.colors.WHITE),
            ],
        )
        self.page.dialog.open = True
        self.page.update()

    # =========================================================
    # 1. ITEMS
    # =========================================================
    def load_items(self):
        self.form = ItemMasterForm(on_submit=self.save_item)
        data = select("items", {"company_id": state.company_id})
        
        brands = sorted(list(set(str(i.get("brand_name")) for i in data if i.get("brand_name"))))
        styles = sorted(list(set(str(i.get("style")) for i in data if i.get("style"))))
        all_sizes_raw = []
        for i in data:
            if isinstance(i.get("sizes"), list):
                all_sizes_raw.extend(i.get("sizes"))
        unique_sizes = sorted(list(set(str(s) for s in all_sizes_raw)))
        self.form.load_metadata(brands, styles, unique_sizes)
        
        for item in data:
            stock = item.get("opening_stock", {})
            item["total_stock"] = sum(int(v) for v in stock.values() if str(v).isdigit()) if isinstance(stock, dict) else 0

        table = TableBuilder(
            [{"key": "item_code", "label": "Code"}, {"key": "item_name", "label": "Name"},
             {"key": "brand_name", "label": "Brand"}, {"key": "style", "label": "Style"},
             {"key": "total_stock", "label": "Total Stock"}, {"key": "pcs_per_inner_box", "label": "Inner"},
             {"key": "boxes_per_outer_box", "label": "Outer"}, {"key": "hsn_code", "label": "HSN"}],
            data, on_edit=self.edit_item, on_delete=self.delete_item
        )
        self.form_area.content = self.form
        self.table_area.content = table
        self._refresh()

    def save_item(self, data):
        data["company_id"] = state.company_id
        try:
            if self.edit_id:
                update("items", data, {"id": self.edit_id})
                self.edit_id = None
            else:
                insert("items", data)
            self.close_modal()
            self.load_items()
            self.page.snack_bar = ft.SnackBar(ft.Text("Item Saved Successfully"), bgcolor="green")
            self.page.snack_bar.open = True
            self.page.update()
        except Exception as e:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error: {e}"), bgcolor="red")
            self.page.snack_bar.open = True
            self.page.update()

    def edit_item(self, row):
        self.edit_id = row["id"]
        self.open_modal()
        self.form.set_values(row)

    def delete_item(self, row):
        self._confirm_delete(f"Delete item '{row.get('item_name')}'?", lambda: (delete("items", {"id": row["id"]}), self.load_items()))

    # =========================================================
    # 2. PRICE LISTS
    # =========================================================
    def load_price_lists(self):
        self.form = PriceListForm(on_submit=self.save_price_list)
        items_data = select("items", {"company_id": state.company_id})
        self.form.load_metadata(items_data)
        data = select("price_lists", {"company_id": state.company_id})
        table = TableBuilder(
            [{"key": "list_name", "label": "List Name"}, {"key": "effective_date", "label": "Date"}, {"key": "price_type", "label": "Type"}],
            data, on_edit=self.edit_price_list, on_delete=self.delete_price_list
        )
        self.form_area.content = self.form
        self.table_area.content = table
        self._refresh()

    def save_price_list(self, data):
        list_header = {"company_id": state.company_id, "list_name": data.get("list_name"), "effective_date": data.get("effective_date"), "price_type": data.get("price_type")}
        items_pricing = data.get("items_pricing", {})
        try:
            is_cloning = data.get("is_clone", False)
            if self.edit_id and not is_cloning:
                update("price_lists", list_header, {"id": self.edit_id})
                price_list_id, self.edit_id = self.edit_id, None
            else:
                res = insert("price_lists", list_header)
                price_list_id = res[0]["id"]
            delete("price_list_items", {"price_list_id": price_list_id})
            for item_id, sizes_dict in items_pricing.items():
                for size_val, rates in sizes_dict.items():
                    insert("price_list_items", {"company_id": state.company_id, "price_list_id": price_list_id, "item_id": item_id, "size_value": size_val, **rates})
            self.close_modal()
            self.load_price_lists()
        except Exception as e: print(f"Error: {e}")

    def edit_price_list(self, row):
        self.edit_id = row["id"]
        db_items = select("price_list_items", {"price_list_id": self.edit_id})
        pricing_state = {}
        for x in db_items:
            i_id = x["item_id"]
            if i_id not in pricing_state: pricing_state[i_id] = {}
            pricing_state[i_id][x["size_value"]] = {"wholesale_rate": x["wholesale_rate"], "retail_rate": x["retail_rate"], "mrp_rate": x["mrp_rate"]}
        
        self.open_modal()
        self.form.set_values(row, pricing_state)

    def delete_price_list(self, row):
        self._confirm_delete(f"Delete price list '{row.get('list_name')}'?", lambda: (delete("price_lists", {"id": row["id"]}), self.load_price_lists()))

    # =========================================================
    # 3. PARTIES
    # =========================================================
    def load_parties(self):
        self.form = PartyMasterForm(on_submit=self.save_party)
        self.form.load_metadata(select("agents", {"company_id": state.company_id}), select("transporters", {"company_id": state.company_id}), select("price_lists", {"company_id": state.company_id}))
        data = select("parties", {"company_id": state.company_id})
        table = TableBuilder(
            [{"key": "code", "label": "Code"}, {"key": "name", "label": "Name"}, {"key": "mobile", "label": "Mobile"},
             {"key": "city", "label": "City"}, {"key": "gstin", "label": "GSTIN"}, {"key": "price_type", "label": "Type"}],
            data, on_edit=self.edit_party, on_delete=self.delete_party
        )
        self.form_area.content = self.form
        self.table_area.content = table
        self._refresh()

    def save_party(self, data):
        data["company_id"] = state.company_id
        try:
            if self.edit_id:
                update("parties", data, {"id": self.edit_id})
                self.edit_id = None
            else:
                insert("parties", data)
            self.close_modal()
            self.load_parties()
        except: pass

    def edit_party(self, row):
        self.edit_id = row["id"]
        self.open_modal()
        self.form.set_values(row)

    def delete_party(self, row):
        self._confirm_delete(f"Delete party '{row.get('name')}'?", lambda: (delete("parties", {"id": row["id"]}), self.load_parties()))

    # =========================================================
    # GENERIC MASTERS
    # =========================================================
    def _generic_loader(self, table_name, fields, cols, save_fn):
        self.form = FormBuilder(fields, on_submit=save_fn)
        data = select(table_name, {"company_id": state.company_id})
        table = TableBuilder(cols, data, on_edit=lambda r: self._generic_edit(r), on_delete=lambda r: self._generic_delete(table_name, r))
        self.form_area.content, self.table_area.content, self.curr_table = self.form, table, table_name
        self._refresh()

    def _generic_edit(self, row):
        self.edit_id = row["id"]
        self.open_modal()
        if hasattr(self.form, "set_values"): self.form.set_values(row)

    def _generic_delete(self, table, row):
        self._confirm_delete(f"Delete entry '{row.get('name') or row.get('item_name')}'?", lambda: (delete(table, {"id": row["id"]}), self.load_tab(self.current_tab)))

    def load_agents(self):
        self._generic_loader("agents", [{"name": "name", "label": "Name *", "required": True}, {"name": "address", "label": "Address"}, {"name": "gstin", "label": "GSTIN"}, {"name": "bank_name", "label": "Bank"}, {"name": "bank_account", "label": "Account"}, {"name": "bank_ifsc", "label": "IFSC"}, {"name": "commission_percent", "label": "Comm %", "type": "number"}],
                             [{"key": "name", "label": "Name"}, {"key": "gstin", "label": "GSTIN"}, {"key": "commission_percent", "label": "Comm. %"}, {"key": "bank_name", "label": "Bank"}], self.save_agent)
    def save_agent(self, data):
        data["company_id"] = state.company_id
        (update("agents", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("agents", data)
        self.close_modal(); self.load_agents()

    def load_transporters(self):
        self._generic_loader("transporters", [{"name": "name", "label": "Name *", "required": True}, {"name": "address", "label": "Address"}, {"name": "gstin", "label": "GSTIN"}],
                             [{"key": "name", "label": "Name"}, {"key": "gstin", "label": "GSTIN"}], self.save_transporter)
    def save_transporter(self, data):
        data["company_id"] = state.company_id
        (update("transporters", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("transporters", data)
        self.close_modal(); self.load_transporters()

    def load_banks(self):
        self._generic_loader("banks", [{"name": "name", "label": "Bank Name *", "required": True}, {"name": "account_no", "label": "Account No"}, {"name": "ifsc_code", "label": "IFSC"}, {"name": "branch", "label": "Branch"}],
                             [{"key": "name", "label": "Bank Name"}, {"key": "account_no", "label": "Account No"}, {"key": "branch", "label": "Branch"}], self.save_bank)
    def save_bank(self, data):
        data["company_id"] = state.company_id
        (update("banks", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("banks", data)
        self.close_modal(); self.load_banks()

    def load_taxes(self):
        self._generic_loader("taxes", [{"name": "name", "label": "Tax Name *", "required": True}, {"name": "tax_type", "label": "Type"}, {"name": "rate_percent", "label": "Rate %", "type": "number"}],
                             [{"key": "name", "label": "Name"}, {"key": "tax_type", "label": "Type"}, {"key": "rate_percent", "label": "Rate %"}], self.save_tax)
    def save_tax(self, data):
        data["company_id"] = state.company_id
        (update("taxes", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("taxes", data)
        self.close_modal(); self.load_taxes()

    def load_staff(self):
        self._generic_loader("staff", [{"name": "name", "label": "Name *", "required": True}, {"name": "designation", "label": "Designation"}],
                             [{"key": "name", "label": "Name"}, {"key": "designation", "label": "Designation"}], self.save_staff)
    def save_staff(self, data):
        data["company_id"] = state.company_id
        (update("staff", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("staff", data)
        self.close_modal(); self.load_staff()

    def load_expense_ledgers(self):
        self._generic_loader("expense_ledgers", [{"name": "name", "label": "Ledger Name *", "required": True}], [{"key": "name", "label": "Ledger Name"}], self.save_ledger)
    def save_ledger(self, data):
        data["company_id"] = state.company_id
        (update("expense_ledgers", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("expense_ledgers", data)
        self.close_modal(); self.load_expense_ledgers()

    def load_general_items(self):
        self._generic_loader("general_items", [{"name": "item_code", "label": "Code"}, {"name": "item_name", "label": "Name *", "required": True}, {"name": "uom", "label": "UOM"}],
                             [{"key": "item_code", "label": "Code"}, {"key": "item_name", "label": "Name"}, {"key": "uom", "label": "UOM"}], self.save_general_item)
    def save_general_item(self, data):
        data["company_id"] = state.company_id
        (update("general_items", data, {"id": self.edit_id}) and setattr(self, "edit_id", None)) if self.edit_id else insert("general_items", data)
        self.close_modal(); self.load_general_items()
