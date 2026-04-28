import flet as ft
import uuid
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert
from core.pdf_gen import pdf_engine, print_pdf

class ChequeTab(ft.Column):
    """
    Combined Receipt & Payment Cheque Screen.
    Payment  → "Paid To"
    Receipt  → "Received From"
    """

    def __init__(self):
        super().__init__()
        self.expand  = True
        self.spacing = 0

        # ── Header ───────────────────────────────────────────
        S = AppStyles.get_input_style()
        self.type_dd = ft.Dropdown(
            label="Type", width=200, value="Receipt",
            options=[ft.dropdown.Option("Receipt"), ft.dropdown.Option("Payment")],
            on_change=self.on_type_change,
            **S
        )
        self.v_no     = ft.TextField(label="Cheque No", width=150, **S)
        self.v_date   = ft.TextField(label="Date",      width=140, value=date.today().isoformat(), **S)
        
        # Dynamic label — changes based on type
        self.party_label = "Received From *"
        self.party_dd = ft.Dropdown(label=self.party_label, width=350, **S)
        self.amount   = ft.TextField(label="Amount (₹) *", width=180, keyboard_type=ft.KeyboardType.NUMBER, **S)
        self.mode_dd  = ft.Dropdown(
            label="Mode", width=180, value="Cash",
            options=[ft.dropdown.Option("Cash"), ft.dropdown.Option("Bank"), ft.dropdown.Option("Cheque")],
            **S
        )
        self.narration = ft.TextField(label="Narration", expand=True, **S)

        # ── History Table ────────────────────────────────────
        self.history_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

        self.controls = [
            self._build_form(),
            ft.Divider(height=1, color="#E2E8F0"),
            self._build_history_header(),
            self.history_col,
        ]

    def _build_form(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=20),
            content=ft.Column([
                # Row 1: Header
                ft.Row([
                    ft.Text("Cheque Entry", size=22, weight="bold", color=AppColors.PRIMARY),
                    ft.Row([self.type_dd, self.v_no, self.v_date], spacing=10),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # Row 2: Transaction Details
                ft.Row([
                    self.party_dd, self.mode_dd, self.amount,
                ], spacing=15),
                
                # Row 3: Narration & Actions
                ft.Row([
                    self.narration,
                    ft.ElevatedButton(
                        "Save & Print", icon=ft.icons.SAVE,
                        on_click=self.save_voucher, height=50,
                        style=AppStyles.primary_button_style(),
                    ),
                    ft.IconButton(ft.icons.REFRESH, on_click=lambda _: self.did_mount(), tooltip="Refresh Data"),
                    ft.IconButton(ft.icons.CLEAR_ALL, on_click=self.clear_form, tooltip="Clear Form"),
                ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=20),
        )

    def _build_history_header(self):
        return ft.Container(
            bgcolor="#F1F5F9",
            padding=ft.padding.symmetric(horizontal=24, vertical=10),
            content=ft.Row([
                ft.Text("DATE",    width=100, size=11, weight="bold"),
                ft.Text("TYPE",    width=100, size=11, weight="bold"),
                ft.Text("PAID TO / RECEIVED FROM", width=250, size=11, weight="bold"),
                ft.Text("MODE",    width=100, size=11, weight="bold"),
                ft.Text("AMOUNT",  expand=True, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ft.Text("ACTION",  width=80, size=11, weight="bold", text_align=ft.TextAlign.CENTER),
            ]),
        )

    def did_mount(self):
        self.load_data()

    def load_data(self):
        if not state.company_id: return
        
        # Load Parties & Agents
        parties = select("parties", {"company_id": state.company_id})
        agents  = select("agents",  {"company_id": state.company_id})
        
        self.party_map = {p['id']: p['name'] for p in parties}
        self.agent_map = {a['id']: a['name'] for a in agents}
        
        opts = []
        for p in parties: opts.append(ft.dropdown.Option(key=f"P|{p['id']}", text=f"Party: {p['name']}"))
        for a in agents:  opts.append(ft.dropdown.Option(key=f"A|{a['id']}", text=f"Agent: {a['name']}"))
        self.party_dd.options = opts
        
        # Load History
        self.load_history()
        if self.page: self.update()

    def load_history(self):
        receipts = select("receipt_vouchers", {"company_id": state.company_id})
        payments = select("payment_vouchers", {"company_id": state.company_id})
        
        history = []
        for r in receipts: history.append({**r, "type": "Receipt"})
        for p in payments: history.append({**p, "type": "Payment"})
        history.sort(key=lambda x: x.get("voucher_date", ""), reverse=True)
        
        self.history_col.controls = []
        for h in history:
            # Resolve name
            p_name = self.party_map.get(h.get("party_id"), "") if h.get("party_id") else self.agent_map.get(h.get("agent_id"), "Unknown")
            h["party_name"] = p_name
            
            # Color for Type
            t_color = ft.colors.GREEN_700 if h["type"] == "Receipt" else ft.colors.RED_700
            # Label for type
            type_label = "RECEIVED FROM" if h["type"] == "Receipt" else "PAID TO"
            
            self.history_col.controls.append(
                ft.Container(
                    bgcolor=ft.colors.WHITE,
                    padding=ft.padding.symmetric(horizontal=24, vertical=12),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
                    content=ft.Row([
                        ft.Text(h.get("voucher_date", "-"), width=100, size=13),
                        ft.Container(
                            content=ft.Text(type_label, size=9, weight="bold", color=ft.colors.WHITE),
                            bgcolor=t_color,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=4,
                            width=100,
                            alignment=ft.alignment.center,
                        ),
                        ft.Text(p_name, width=250, size=13, weight="w500"),
                        ft.Text(h.get("mode", "-"), width=100, size=13),
                        ft.Text(f"₹{float(h.get('amount', 0)):,.2f}", expand=True, size=13, weight="bold", text_align=ft.TextAlign.RIGHT, color=AppColors.PRIMARY),
                        ft.Container(
                            width=120, alignment=ft.alignment.center_right,
                            content=ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.ACCOUNT_BALANCE,
                                    tooltip="Print Cheque",
                                    icon_color=ft.colors.TEAL_700,
                                    visible=(h["type"] == "Payment" and str(h.get("mode", "")).lower() == "cheque"),
                                    on_click=lambda e, voucher=h: self.print_cheque(voucher)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.PRINT,
                                    tooltip="Print",
                                    icon_color=ft.colors.BLUE_700,
                                    on_click=lambda e, voucher=h: self.print_entry(voucher)
                                )
                            ], alignment=ft.MainAxisAlignment.END, spacing=0)
                        )
                    ])
                )
            )
        if self.page: self.update()

    def print_entry(self, voucher):
        """Print a receipt/payment entry directly to the printer."""
        try:
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            # Set correct label
            if voucher.get("type") == "Payment":
                voucher["direction_label"] = "Paid To"
            else:
                voucher["direction_label"] = "Received From"
            
            pdf_path = pdf_engine.generate_voucher(voucher, company)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing: {ex}", "red")

    def on_type_change(self, e):
        prefix = "RV-" if self.type_dd.value == "Receipt" else "PV-"
        self.v_no.value = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
        # Update party dropdown label
        if self.type_dd.value == "Receipt":
            self.party_dd.label = "Received From *"
        else:
            self.party_dd.label = "Paid To *"
        self.update()

    def save_voucher(self, e):
        if not self.party_dd.value or not self.amount.value:
            self._snack("Please fill all required fields!", "red")
            return
        
        try:
            v_type = self.type_dd.value
            table  = "receipt_vouchers" if v_type == "Receipt" else "payment_vouchers"
            
            party_val = str(self.party_dd.value or "")
            if not party_val or "|" not in party_val:
                raise Exception("Invalid party selection")
                
            p_val = party_val.split("|")
            p_type, p_id = p_val[0], p_val[1]
            
            # Ensure v_no is populated
            prefix = "RV-" if v_type == "Receipt" else "PV-"
            v_no_val = self.v_no.value.strip() if self.v_no.value else f"{prefix}{uuid.uuid4().hex[:6].upper()}"

            data = {
                "company_id":   state.company_id,
                "voucher_no":   v_no_val,
                "voucher_date": self.v_date.value,
                "amount":       float(self.amount.value),
                "mode":         self.mode_dd.value,
                "narration":    self.narration.value
            }
            if p_type == "P": data["party_id"] = p_id
            else:             data["agent_id"] = p_id
            
            res = insert(table, data)
            if not res: raise Exception("Failed to save entry")
            
            # Resolve party name
            party_name = "Unknown"
            if party_val and "|" in party_val:
                parts = party_val.split("|")
                p_id = parts[1]
                p_table = "parties" if parts[0] == "P" else "agents"
                p_data = select(p_table, {"id": p_id})
                if p_data: party_name = p_data[0]["name"]
            
            data["party_name"] = party_name
            data["type"] = v_type
            data["direction_label"] = "Paid To" if v_type == "Payment" else "Received From"
            
            # Fetch company details for print
            comp_data = select("companies", {"id": state.company_id})
            company = comp_data[0] if comp_data else {}
            
            # Generate and send directly to printer
            pdf_path = pdf_engine.generate_voucher(data, company)
            print_pdf(pdf_path)

            # Record in ledger_entries
            insert("ledger_entries", {
                "company_id":   state.company_id,
                "entry_date":   self.v_date.value,
                "account_type": "Party" if p_type == "P" else "Agent",
                "account_id":   p_id,
                "ref_type":     v_type,
                "ref_id":       data["voucher_no"],
                "debit":        data["amount"] if v_type == "Payment" else 0,
                "credit":       data["amount"] if v_type == "Receipt" else 0,
                "narration":    data["narration"]
            })

            self._snack(f"✅ {v_type} saved successfully!", "green")
            self.clear_form(None)
            self.load_history()
            self.update()

        except Exception as ex:
            self._snack(f"Error: {ex}", "red")

    def clear_form(self, e):
        prefix = "RV-" if self.type_dd.value == "Receipt" else "PV-"
        self.v_no.value = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
        self.amount.value = ""
        self.narration.value = ""
        self.party_dd.value = None
        if self.page: self.update()

    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def print_cheque(self, voucher):
        """Print a cheque directly to the system printer."""
        try:
            # Resolve payee name from party_id or agent_id
            payee = "Unknown Payee"
            if voucher.get("party_id"):
                p_data = select("parties", {"id": voucher["party_id"]})
                if p_data: payee = p_data[0]["name"]
            elif voucher.get("agent_id"):
                a_data = select("agents", {"id": voucher["agent_id"]})
                if a_data: payee = a_data[0]["name"]
            
            amount = voucher.get("amount", 0)
            date_str = str(voucher.get("voucher_date", ""))[:10]
            ref_no = voucher.get("ref_no", voucher.get("voucher_no", ""))
            
            pdf_path = pdf_engine.generate_cheque(payee, amount, date_str, ref_no)
            print_pdf(pdf_path)
        except Exception as ex:
            self._snack(f"Error printing cheque: {ex}", "red")
