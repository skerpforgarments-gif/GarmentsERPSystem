import flet as ft
import json
import os
from datetime import date

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import insert, select, update

class SettingsScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 20

        # TABS
        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self.on_tab_change,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            divider_color="#F0F0F0",
            tabs=[
                ft.Tab(text="Workspace & Company"),
                ft.Tab(text="Utility & Admin"),
            ],
        )

        self.content_area = ft.Container(expand=True)

        self.content = ft.Column(
            controls=[
                ft.Text("Platform Settings", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.tabs,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.content_area
            ],
            expand=True
        )

    def did_mount(self):
        if not state.current_user:
            return
        self.load_workspace_tab()

    def on_tab_change(self, e):
        if self.tabs.selected_index == 0:
            self.load_workspace_tab()
        else:
            self.load_utility_tab()
        if self.page: self.update()

    # =========================================================
    # TAB 1: WORKSPACE
    # =========================================================
    def load_workspace_tab(self):
        style_args = {
            "dense": True, "text_size": 13, "height": 45,
            "border_radius": AppStyles.BUTTON_RADIUS, "border_color": "#E2E8F0",
            "focused_border_color": AppColors.PRIMARY, "bgcolor": "#F8FAFC",
            "label_style": ft.TextStyle(color=AppColors.TEXT_SUB, size=12)
        }

        self.company_code = ft.TextField(label="Company Code", width=150, **style_args)
        self.branch_code = ft.TextField(label="Branch Code", width=150, **style_args)
        self.company_name = ft.TextField(label="Company Name *", width=350, **style_args)
        self.company_address = ft.TextField(label="Address", width=400, multiline=True, min_lines=2, max_lines=3, **style_args)
        self.company_gst = ft.TextField(label="GST Details (GSTIN)", width=300, **style_args)
        self.company_fy = ft.TextField(label="Financial Period (e.g. 2025-2026)", width=250, **style_args)
        self.create_btn = ft.ElevatedButton("Create New Business Profile", on_click=self.handle_create_company, style=AppStyles.primary_button_style(), height=45)
        
        self.company_dropdown = ft.Dropdown(label="Switch Workspace", width=400, on_change=self.select_company, **style_args)
        self.current_company_text = ft.Text(state.current_company.get("name") if state.current_company else "No active workspace selected", size=14, color=AppColors.TEXT_SUB)

        self.content_area.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("BUSINESS SETUP", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Text("Initialize a new company profile to manage multiple divisions.", size=13, color=AppColors.TEXT_SUB),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    ft.Row([self.company_code, self.branch_code], spacing=12),
                    self.company_name,
                    self.company_address,
                    ft.Row([self.company_gst, self.company_fy], spacing=12),
                    self.create_btn,
                ], spacing=10),
                padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS, shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0")
            ),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.Container(
                content=ft.Column([
                    ft.Text("WORKSPACE MANAGEMENT", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Text("Switch between your authorized business entities.", size=13, color=AppColors.TEXT_SUB),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    self.company_dropdown,
                    ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                    ft.Row([ft.Text("ACTIVE ENTITY:", weight="bold", size=12, color=AppColors.TEXT_HEADER), self.current_company_text], spacing=10)
                ], spacing=10),
                padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS, shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0")
            )
        ], scroll=ft.ScrollMode.AUTO)
        
        self.load_companies_dropdown()

    def load_companies_dropdown(self):
        try:
            companies = select("companies")
            self.company_dropdown.options = [ft.dropdown.Option(key=str(c["id"]), text=c["name"]) for c in companies]
            if state.company_id:
                self.company_dropdown.value = str(state.company_id)
        except Exception as e:
            print("Error loading companies:", e)
        if self.page: self.update()

    def handle_create_company(self, e):
        name = self.company_name.value
        if not name: return
        try:
            insert("companies", {
                "name": name,
                "company_code": self.company_code.value or None,
                "branch_code": self.branch_code.value or None,
                "address": self.company_address.value or None,
                "gst_details": self.company_gst.value or None,
                "financial_period": self.company_fy.value or None,
                "user_id": state.current_user.id
            })
            self.company_code.value = ""
            self.branch_code.value = ""
            self.company_name.value = ""
            self.company_address.value = ""
            self.company_gst.value = ""
            self.company_fy.value = ""
            self.load_companies_dropdown()
        except Exception as ex:
            print("Error creating company:", ex)
        if self.page: self.update()

    def select_company(self, e):
        company_id = self.company_dropdown.value
        try:
            companies = select("companies")
            company = next(c for c in companies if str(c["id"]) == company_id)
            state.set_company(company)
            self.current_company_text.value = company["name"]
        except Exception as ex:
            print("Error selecting company:", ex)
        if self.page: self.update()

    # =========================================================
    # TAB 2: UTILITY & ADMIN
    # =========================================================
    def load_utility_tab(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first", color="red")
            return
            
        self.flow_switch = ft.Switch(
            label="Direct Invoice Mode (Skip Packing/Transport)", 
            value=state.settings.get("direct_invoice", False),
            on_change=self.save_all_settings,
            active_color=AppColors.PRIMARY
        )

        self.tax_calc_switch = ft.Switch(
            label="Tax on Gross Amount (Apply Discount after Tax)", 
            value=state.settings.get("tax_on_gross", False),
            on_change=self.save_all_settings,
            active_color=AppColors.PRIMARY
        )
        
        self.status_msg = ft.Text("", color=AppColors.PRIMARY)

        self.content_area.content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("SYSTEM PREFERENCES", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    self.flow_switch,
                    ft.Text("If enabled, Final Sales Invoices will pull items directly from Sales Orders instead of waiting for Transport Invoices.", size=12, color=AppColors.TEXT_SUB),
                    ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                    self.tax_calc_switch,
                    ft.Text("If enabled, GST will be calculated on the full Gross amount before any multi-tier discounts are subtracted.", size=12, color=AppColors.TEXT_SUB)
                ], spacing=10),
                padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS, shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0")
            ),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.Container(
                content=ft.Column([
                    ft.Text("DATA MANAGEMENT (LOCAL)", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    ft.Row([
                        ft.ElevatedButton("Backup Database", icon=ft.icons.DOWNLOAD, on_click=self.do_backup, bgcolor=ft.colors.BLUE_GREY_700, color=ft.colors.WHITE),
                        ft.ElevatedButton("Restore Backup", icon=ft.icons.UPLOAD, on_click=self.do_restore, bgcolor=ft.colors.RED_700, color=ft.colors.WHITE),
                    ], spacing=15)
                ], spacing=10),
                padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS, shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0")
            ),
            ft.Divider(height=20, color=ft.colors.TRANSPARENT),
            ft.Container(
                content=ft.Column([
                    ft.Text("YEAR END PROCESS", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.Text("Warning: This calculates closing balances for all ledgers and inserts an 'Opening Balance' for April 1st.", size=12, color=AppColors.DANGER),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    ft.ElevatedButton("Run Financial Rollover", icon=ft.icons.NEXT_PLAN, on_click=self.run_year_end, bgcolor=AppColors.PRIMARY, color=ft.colors.WHITE),
                ], spacing=10),
                padding=24, bgcolor=AppColors.BG_CARD, border_radius=AppStyles.RADIUS, shadow=AppStyles.CARD_SHADOW, border=ft.border.all(1, "#F0F0F0")
            ),
            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
            self.status_msg
        ], scroll=ft.ScrollMode.AUTO)

    def save_all_settings(self, e):
        state.settings["direct_invoice"] = self.flow_switch.value
        state.settings["tax_on_gross"]   = self.tax_calc_switch.value
        state.save_settings()
        self.status_msg.value = "Preferences saved."
        if self.page: self.update()

    def do_backup(self, e):
        try:
            self.status_msg.value = "Fetching data for backup..."
            if self.page: self.update()
            
            tables = [
                "parties", "agents", "items", "transporters", "banks", "taxes", "staff",
                "expense_ledgers", "general_items", "price_lists", "price_list_items",
                "orders", "order_items", "packing_slips", "packing_slip_items",
                "transport_invoices", "transport_invoice_items",
                "final_invoices", "final_invoice_items",
                "receipt_vouchers", "payment_vouchers", "ledger_entries",
                "purchase_orders", "purchase_order_items"
            ]
            export_data = {}
            for t in tables:
                try:
                    export_data[t] = select(t, {"company_id": state.company_id})
                except:
                    export_data[t] = []
                
            filename = f"backup_{date.today().isoformat()}.json"
            filepath = os.path.join(os.getcwd(), filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, default=str, ensure_ascii=False, indent=2)
                
            self.status_msg.value = f"✅ Backup successful! Saved to {filepath}"
        except Exception as ex:
            self.status_msg.value = f"❌ Backup failed: {ex}"
        if self.page: self.update()

    def do_restore(self, e):
        backup_path = os.path.join(os.getcwd(), "backup.json")
        if not os.path.exists(backup_path):
            self.status_msg.value = "❌ No 'backup.json' found in the application root folder. Please copy your backup file there and rename it to 'backup.json'."
            if self.page: self.update()
            return
            
        try:
            self.status_msg.value = "Restoring data from backup.json..."
            if self.page: self.update()
            
            with open(backup_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            total_records = 0
            for table_name, rows in data.items():
                for row in rows:
                    # Remove id to avoid primary key conflicts — DB will auto-generate
                    row.pop("id", None)
                    row.pop("created_at", None)
                    # Ensure company_id points to current company
                    if "company_id" in row:
                        row["company_id"] = state.company_id
                    try:
                        insert(table_name, row)
                        total_records += 1
                    except Exception as row_err:
                        print(f"Skipped {table_name} row: {row_err}")
            
            self.status_msg.value = f"✅ Restore complete! Imported {total_records} records."
        except Exception as ex:
            self.status_msg.value = f"❌ Restore failed: {ex}"
        if self.page: self.update()

    def run_year_end(self, e):
        try:
            self.status_msg.value = "Running Year-End Rollover..."
            if self.page: self.update()
            
            ledger = select("ledger_entries", {"company_id": state.company_id})
            balances = {}
            for entry in ledger:
                pid = str(entry.get("party_id"))
                if not entry.get("party_id"): continue
                if pid not in balances: balances[pid] = {"debit": 0, "credit": 0}
                balances[pid]["debit"] += float(entry.get("debit", 0) or 0)
                balances[pid]["credit"] += float(entry.get("credit", 0) or 0)
                
            next_yr = date.today().year if date.today().month > 3 else date.today().year - 1
            op_date = f"{next_yr}-04-01"
            
            count = 0
            for pid, v in balances.items():
                net = v["debit"] - v["credit"]
                if round(net, 2) != 0:
                    insert("ledger_entries", {
                        "company_id": state.company_id,
                        "party_id": pid,
                        "debit": net if net > 0 else 0,
                        "credit": abs(net) if net < 0 else 0,
                        "balance": 0, # Note: balance logic usually handled by a running sum view, keeping 0 here for raw insert
                        "created_at": op_date + "T00:00:00Z"
                    })
                    count += 1
                    
            self.status_msg.value = f"✅ Year-End successful! Carried forward balances for {count} parties."
        except Exception as ex:
            self.status_msg.value = f"❌ Year-End failed: {ex}"
        if self.page: self.update()
