import flet as ft
import uuid
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert, update, delete, get_next_doc_no

# ── Deterministic Cash Account ─────────────────────────────
# Every company gets a virtual "Cash Account" without needing
# to add one manually. We use uuid5 so the ID is always the
# same for a given company_id.
CASH_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

def get_cash_account_id(company_id: str) -> str:
    """Return a deterministic UUID for the company's virtual Cash account."""
    return str(uuid.uuid5(CASH_NAMESPACE, company_id))


class FinanceScreen(ft.Column):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.spacing = 0

        self.current_tab = "ledger"
        self.selected_party_id = None

        # ── Header Section ───────────────────────────────────
        self.title_text = ft.Text("Financial Management", size=24, weight="bold", color=AppColors.PRIMARY)

        # ── Statistics Row ───────────────────────────────────
        self.stat_receivable = self._build_stat_card("Total Receivable", "₹ 0.00", ft.icons.ARROW_DOWNWARD, "green")
        self.stat_payable    = self._build_stat_card("Total Payable",    "₹ 0.00", ft.icons.ARROW_UPWARD, "red")

        # ── Navigation Tabs ──────────────────────────────────
        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_tab_change,
            tabs=[
                ft.Tab(text="General Ledger", icon=ft.icons.ACCOUNT_BALANCE_WALLET),
                ft.Tab(text="Cash/Bank Receipt", icon=ft.icons.ADD_CARD),
                ft.Tab(text="Cash/Bank Payment", icon=ft.icons.PAYMENT),
            ],
            divider_color="#F1F5F9",
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB
        )

        # ── Content Area ─────────────────────────────────────
        self.content_area = ft.Container(expand=True, padding=ft.padding.only(top=10))

        self.controls = [
            self._build_top_bar(),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=24, vertical=20),
                expand=True,
                content=ft.Column([
                    ft.Row([self.stat_receivable, self.stat_payable], spacing=20),
                    ft.Container(height=20),
                    self.tabs,
                    self.content_area
                ], spacing=0, expand=True)
            )
        ]

    def _build_top_bar(self):
        return ft.Container(
            bgcolor=ft.colors.WHITE,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#E2E8F0")),
            content=ft.Row([
                ft.Column([
                    self.title_text,
                    ft.Text("Manage ledgers, receipts, and payments", size=13, color=AppColors.TEXT_SUB),
                ]),
                ft.Row([
                    ft.ElevatedButton("Refresh Data", icon=ft.icons.REFRESH, on_click=lambda _: self.did_mount(), style=AppStyles.secondary_button_style()),
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    def _build_stat_card(self, label, value, icon, color):
        return ft.Container(
            expand=True,
            bgcolor=ft.colors.WHITE,
            padding=20,
            border_radius=12,
            border=ft.border.all(1, "#E2E8F0"),
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=color, size=24),
                    bgcolor=ft.colors.with_opacity(0.1, color),
                    padding=12,
                    border_radius=10,
                ),
                ft.Column([
                    ft.Text(label, size=12, color=AppColors.TEXT_SUB, weight="w500"),
                    ft.Text(value, size=20, weight="bold", color=AppColors.TEXT_HEADER),
                ], spacing=2)
            ], spacing=15)
        )

    def did_mount(self):
        self._update_stats()
        self._on_tab_change(None)

    # ── Stats Dashboard (Accurate double-entry) ──────────────
    def _update_stats(self, acc_id=None):
        if not state.company_id: return

        if acc_id:
            # Dynamic: show stats for the selected account only
            entries = select("ledger_entries", {"account_id": acc_id, "company_id": state.company_id})
            total_debit = sum(float(e.get("debit", 0)) for e in entries)
            total_credit = sum(float(e.get("credit", 0)) for e in entries)
            self.stat_receivable.content.controls[1].controls[0].value = "Total Debit"
            self.stat_payable.content.controls[1].controls[0].value = "Total Credit"
            self.stat_receivable.content.controls[1].controls[1].value = f"₹ {total_debit:,.2f}"
            self.stat_payable.content.controls[1].controls[1].value = f"₹ {total_credit:,.2f}"
        else:
            # Default: show overall receivable/payable
            entries = select("ledger_entries", {"company_id": state.company_id})
            party_balances = {}
            for e in entries:
                if e.get("account_type") == "Party":
                    pid = str(e.get("account_id", ""))
                    party_balances[pid] = party_balances.get(pid, 0) + (float(e.get("debit", 0)) - float(e.get("credit", 0)))
            receivable = sum(b for b in party_balances.values() if b > 0)
            payable = sum(abs(b) for b in party_balances.values() if b < 0)
            self.stat_receivable.content.controls[1].controls[0].value = "Total Receivable"
            self.stat_payable.content.controls[1].controls[0].value = "Total Payable"
            self.stat_receivable.content.controls[1].controls[1].value = f"₹ {receivable:,.2f}"
            self.stat_payable.content.controls[1].controls[1].value = f"₹ {payable:,.2f}"

        if self.page: self.update()

    def _on_tab_change(self, e):
        idx = self.tabs.selected_index
        if idx == 0: self._show_ledger_view()
        elif idx == 1: self._show_voucher_entry("Receipt")
        elif idx == 2: self._show_voucher_entry("Payment")

    # ══════════════════════════════════════════════════════════
    # ── GENERAL LEDGER VIEW ──────────────────────────────────
    # ══════════════════════════════════════════════════════════
    def _show_ledger_view(self):
        S = AppStyles.get_input_style()

        # 1. Type Selector
        self.v_type_dd = ft.Dropdown(
            label="Account Type", width=200,
            options=[
                ft.dropdown.Option("Party"),
                ft.dropdown.Option("Expense"),
                ft.dropdown.Option("Bank"),
                ft.dropdown.Option("Cash"),
            ],
            value="Party", **S
        )

        # 2. Account Selector
        self.v_acc_dd = ft.Dropdown(label="Select Account", width=350, **S)

        # 3. Status Filter
        self.v_filter_dd = ft.Dropdown(
            label="Status", width=180,
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("Pending (Unpaid)"),
                ft.dropdown.Option("Settled (Paid)"),
            ],
            value="All", **S
        )

        def on_account_change(e):
            acc_id = self.v_acc_dd.value
            if not acc_id: return
            self._update_stats(acc_id)
            self._render_statement(acc_id, self.v_filter_dd.value)

        def on_filter_change(e):
            acc_id = self.v_acc_dd.value
            if acc_id:
                self._render_statement(acc_id, self.v_filter_dd.value)
            elif self.v_type_dd.value == "Cash":
                cash_id = get_cash_account_id(state.company_id)
                self._render_statement(cash_id, self.v_filter_dd.value)

        self.v_acc_dd.on_change = on_account_change
        self.v_filter_dd.on_change = on_filter_change

        def load_ledger_accounts(e=None):
            self._update_stats()  # Reset to overall stats
            if self.v_type_dd.value == "Party":
                data = select("parties", {"company_id": state.company_id})
                self.v_acc_dd.label = "Select Party"
                self.v_acc_dd.options = [ft.dropdown.Option(str(d["id"]), d["name"]) for d in data]
                self.v_acc_dd.visible = True
            elif self.v_type_dd.value == "Expense":
                data = select("expense_ledgers", {"company_id": state.company_id})
                self.v_acc_dd.label = "Select Expense"
                self.v_acc_dd.options = [ft.dropdown.Option(str(d["id"]), d["name"]) for d in data]
                self.v_acc_dd.visible = True
            elif self.v_type_dd.value == "Bank":
                data = select("banks", {"company_id": state.company_id})
                self.v_acc_dd.label = "Select Bank"
                self.v_acc_dd.options = [ft.dropdown.Option(str(d["id"]), d["name"]) for d in data]
                self.v_acc_dd.visible = True
            elif self.v_type_dd.value == "Cash":
                self.v_acc_dd.visible = False
                cash_id = get_cash_account_id(state.company_id)
                self._update_stats(cash_id)
                self._render_statement(cash_id, self.v_filter_dd.value)

            self.v_acc_dd.value = None
            if self.v_acc_dd.page: self.v_acc_dd.update()

        self.v_type_dd.on_change = load_ledger_accounts
        load_ledger_accounts()

        self.statement_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

        self.content_area.content = ft.Column([
            ft.Row([self.v_type_dd, self.v_acc_dd, self.v_filter_dd], spacing=15, alignment=ft.MainAxisAlignment.START),
            ft.Container(height=20),
            ft.Container(
                bgcolor="#F8FAFC",
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                border_radius=8,
                content=ft.Row([
                    ft.Text("DATE",    width=100, size=11, weight="bold"),
                    ft.Text("PARTICULARS", expand=True, size=11, weight="bold"),
                    ft.Text("REF NO",  width=120, size=11, weight="bold"),
                    ft.Text("DEBIT",   width=100, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                    ft.Text("CREDIT",  width=100, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                    ft.Text("BALANCE", width=120, size=11, weight="bold", text_align=ft.TextAlign.RIGHT),
                ])
            ),
            self.statement_col
        ], spacing=0, expand=True)

        if self.page: self.update()

    def _load_cash_statement(self):
        cash_id = get_cash_account_id(state.company_id)
        self._render_statement(cash_id, "All")

    def _render_statement(self, acc_id, status_filter="All"):
        """Render ledger statement with optional status filter."""
        entries = select("ledger_entries", {"account_id": acc_id, "company_id": state.company_id})
        entries.sort(key=lambda x: x.get("entry_date") or x.get("created_at") or "")

        # Apply filter
        # "Pending" = Invoice/Order entries (debts created, not yet settled)
        # "Settled" = Receipt/Payment entries (money exchanged)
        PENDING_TYPES = {"Sales Invoice", "Purchase Order"}
        SETTLED_TYPES = {"Receipt Voucher", "Payment Voucher"}

        if status_filter == "Pending (Unpaid)":
            entries = [e for e in entries if e.get("ref_type", "") in PENDING_TYPES]
        elif status_filter == "Settled (Paid)":
            entries = [e for e in entries if e.get("ref_type", "") in SETTLED_TYPES]

        self.statement_col.controls = []
        balance = 0.0
        display_rows = []

        for entry in entries:
            deb = float(entry.get("debit", 0))
            cre = float(entry.get("credit", 0))
            balance += (deb - cre)

            display_rows.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, "#F1F5F9")),
                    content=ft.Row([
                        ft.Text(entry.get("entry_date", ""), width=100, size=13),
                        ft.Text(entry.get("narration") or entry.get("ref_type", ""), expand=True, size=13),
                        ft.Text(entry.get("ref_id", ""), width=120, size=13),
                        ft.Text(f"{deb:,.2f}" if deb else "-", width=100, size=13, text_align=ft.TextAlign.RIGHT, color="red" if deb else None),
                        ft.Text(f"{cre:,.2f}" if cre else "-", width=100, size=13, text_align=ft.TextAlign.RIGHT, color="green" if cre else None),
                        ft.Text(f"{abs(balance):,.2f} {'DR' if balance >= 0 else 'CR'}", width=120, size=13, weight="bold", text_align=ft.TextAlign.RIGHT),
                    ])
                )
            )

        # Reverse to show latest on top
        display_rows.reverse()
        self.statement_col.controls = display_rows

        if not entries:
            self.statement_col.controls = [ft.Container(padding=40, content=ft.Text("No transactions found for this account.", color="#999"))]

        if self.page: self.update()

    # ══════════════════════════════════════════════════════════
    # ── VOUCHER ENTRY (Receipt / Payment) ────────────────────
    # ══════════════════════════════════════════════════════════
    def _show_voucher_entry(self, mode):
        S = AppStyles.get_input_style()

        # 1. Account Type (Only for Payment, Receipt is always Party)
        v_acc_type = ft.Dropdown(
            label="Account Type", width=200,
            options=[ft.dropdown.Option("Party"), ft.dropdown.Option("Expense")],
            value="Party", visible=(mode == "Payment"), **S
        )

        # 2. Account Dropdown
        v_acc_dd = ft.Dropdown(label="Select Account", width=350, **S)

        # 3. Bank Selector (Hidden by default, shown for non-cash modes)
        banks = select("banks", {"company_id": state.company_id})
        v_bank_dd = ft.Dropdown(
            label="Select Bank", width=250,
            options=[ft.dropdown.Option(str(b["id"]), b["name"]) for b in banks],
            visible=False, **S
        )

        def on_mode_change(e):
            v_bank_dd.visible = (v_mode.value != "Cash")
            if v_bank_dd.page: v_bank_dd.update()

        def load_accounts(e=None):
            if mode == "Receipt" or v_acc_type.value == "Party":
                p_types = ["Customer", "Both"] if mode == "Receipt" else ["Supplier", "Both"]
                data = select("parties", {"company_id": state.company_id, "party_type": p_types})
                v_acc_dd.label = "Party Account"
            else:
                data = select("expense_ledgers", {"company_id": state.company_id})
                v_acc_dd.label = "Expense Account"

            v_acc_dd.options = [ft.dropdown.Option(str(d["id"]), d["name"]) for d in data]
            if v_acc_dd.page: v_acc_dd.update()

        v_acc_type.on_change = load_accounts
        load_accounts()  # Initial load

        v_date   = ft.TextField(label="Date", width=150, value=date.today().isoformat(), **S)
        v_amount = ft.TextField(label="Amount", width=150, **S)
        v_mode   = ft.Dropdown(
            label="Payment Mode", width=200,
            options=[ft.dropdown.Option(k) for k in ["Cash", "Bank Transfer", "Cheque", "UPI"]],
            value="Cash", on_change=on_mode_change, **S
        )
        v_ref = ft.TextField(label="Reference/Notes", expand=True, **S)

        def save_voucher(e):
            if not v_acc_dd.value or not v_amount.value:
                self._snack("Please fill account and amount", "red")
                return

            # Validate: if non-cash mode, bank must be selected
            if v_mode.value != "Cash" and not v_bank_dd.value:
                self._snack("Please select a bank for non-cash payments", "red")
                return

            try:
                amt = float(v_amount.value)
                table = "receipt_vouchers" if mode == "Receipt" else "payment_vouchers"
                v_no = get_next_doc_no(table, "R" if mode == "Receipt" else "P", state.company_id, "voucher_no")

                is_expense = (mode == "Payment" and v_acc_type.value == "Expense")

                # ── Save Voucher Record ──────────────────────
                v_data = {
                    "company_id":   state.company_id,
                    "voucher_no":   v_no,
                    "voucher_date": v_date.value,
                    "amount":       amt,
                    "mode":         v_mode.value,
                    "bank_id":      v_bank_dd.value if v_mode.value != "Cash" else None,
                    "narration":    v_ref.value
                }
                if is_expense:
                    v_data["expense_id"] = v_acc_dd.value
                else:
                    v_data["party_id"] = v_acc_dd.value

                insert(table, v_data)

                # ═════════════════════════════════════════════
                # DOUBLE-ENTRY BOOKKEEPING
                # ═════════════════════════════════════════════

                # ── ENTRY 1: Party / Expense Side ────────────
                # Receipt → Credit the party (their debt decreases)
                # Payment → Debit the expense/party (cost increases / their debt decreases)
                insert("ledger_entries", {
                    "company_id":   state.company_id,
                    "account_id":   v_acc_dd.value,
                    "account_type": "Expense" if is_expense else "Party",
                    "debit":        0 if mode == "Receipt" else amt,
                    "credit":       amt if mode == "Receipt" else 0,
                    "ref_id":       v_no,
                    "ref_type":     f"{mode} Voucher",
                    "entry_date":   v_date.value,
                    "narration":    v_ref.value
                })

                # ── ENTRY 2: Cash / Bank Side ────────────────
                # Receipt → Debit cash/bank (money comes IN)
                # Payment → Credit cash/bank (money goes OUT)
                if v_mode.value == "Cash":
                    cash_bank_id = get_cash_account_id(state.company_id)
                    cash_bank_type = "Cash"
                else:
                    cash_bank_id = v_bank_dd.value
                    cash_bank_type = "Bank"

                insert("ledger_entries", {
                    "company_id":   state.company_id,
                    "account_id":   cash_bank_id,
                    "account_type": cash_bank_type,
                    "debit":        amt if mode == "Receipt" else 0,
                    "credit":       0 if mode == "Receipt" else amt,
                    "ref_id":       v_no,
                    "ref_type":     f"{mode} Voucher",
                    "entry_date":   v_date.value,
                    "narration":    v_ref.value
                })

                self._snack(f"✅ {mode} saved successfully!", "green")
                self._on_tab_change(None)  # Refresh
                self._update_stats()
            except Exception as ex:
                self._snack(f"Error: {ex}", "red")

        self.content_area.content = ft.Column([
            ft.Container(
                padding=20,
                bgcolor="#F8FAFC",
                border_radius=12,
                content=ft.Column([
                    ft.Text(f"New {mode} Entry", weight="bold", size=16),
                    ft.Row([v_acc_type, v_acc_dd, v_date], spacing=10),
                    ft.Row([v_amount, v_mode, v_bank_dd, v_ref], spacing=10),
                    ft.Row([
                        ft.ElevatedButton(f"Save {mode}", icon=ft.icons.SAVE, on_click=save_voucher, style=AppStyles.primary_button_style(), height=45),
                    ], alignment=ft.MainAxisAlignment.END)
                ], spacing=15)
            ),
            ft.Container(height=30),
            ft.Text(f"Recent {mode}s", weight="bold", size=16),
            self._build_recent_vouchers(mode)
        ], scroll=ft.ScrollMode.AUTO)

        if self.page: self.update()

    # ── Recent Vouchers List ─────────────────────────────────
    def _build_recent_vouchers(self, mode):
        table = "receipt_vouchers" if mode == "Receipt" else "payment_vouchers"
        data = select(table, {"company_id": state.company_id})
        data.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Fetch name maps
        parties  = {str(p["id"]): p["name"] for p in select("parties", {"company_id": state.company_id})}
        expenses = {str(e["id"]): e["name"] for e in select("expense_ledgers", {"company_id": state.company_id})}
        bank_map = {str(b["id"]): b["name"] for b in select("banks", {"company_id": state.company_id})}

        lv = ft.Column(spacing=10)
        for d in data[:10]:  # Show last 10
            acc_name = parties.get(str(d.get("party_id")), expenses.get(str(d.get("expense_id")), "Unknown"))

            if d.get("mode") == "Cash":
                source_label = "Cash"
            elif d.get("bank_id"):
                source_label = bank_map.get(str(d.get("bank_id")), "Bank")
            else:
                source_label = d.get("mode", "")

            lv.controls.append(
                ft.Container(
                    padding=15, bgcolor=ft.colors.WHITE, border_radius=10, border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Row([
                        ft.Icon(
                            ft.icons.ARROW_CIRCLE_DOWN if mode == "Receipt" else ft.icons.ARROW_CIRCLE_UP,
                            color="green" if mode == "Receipt" else "red"
                        ),
                        ft.Column([
                            ft.Text(acc_name, weight="bold"),
                            ft.Text(f"{d.get('voucher_no')} | {d.get('voucher_date')} | {source_label}", size=12, color=AppColors.TEXT_SUB),
                        ], expand=True),
                        ft.Text(f"₹ {float(d.get('amount', 0)):,.2f}", weight="bold", size=16)
                    ])
                )
            )
        return lv

    # ── Utilities ────────────────────────────────────────────
    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()
