import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert
from components.table import TableBuilder
from components.form import FormBuilder


class FinanceScreen(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.padding = 10

        # =========================
        # TABS
        # =========================
        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self.on_tab_change,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SUB,
            divider_color="#F0F0F0",
            tabs=[
                ft.Tab(text="Ledger"),
                ft.Tab(text="Receipts"),
                ft.Tab(text="Payments"),
            ]
        )

        self.content_area = ft.Container(expand=True)

        self.content = ft.Column(
            controls=[
                ft.Text("Financial Management", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.tabs,
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                self.content_area
            ],
            expand=True
        )

    def did_mount(self):
        self.load_ledger()

    # =========================================================
    # TAB SWITCH
    # =========================================================
    def on_tab_change(self, e):
        index = self.tabs.selected_index

        if index == 0:
            self.load_ledger()
        elif index == 1:
            self.load_receipts()
        elif index == 2:
            self.load_payments()

        if self.page:
            self.update()

    # =========================================================
    # LEDGER VIEW
    # =========================================================
    def load_ledger(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        data = select("ledger_entries", {"company_id": state.company_id})

        columns = [
            {"key": "party_id", "label": "Party"},
            {"key": "debit", "label": "Debit"},
            {"key": "credit", "label": "Credit"},
            {"key": "balance", "label": "Balance"},
        ]

        table = TableBuilder(columns, data)

        self.content_area.content = table

    # =========================================================
    # RECEIPTS
    # =========================================================
    def load_receipts(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        fields = [
            {"name": "party_id", "label": "Party ID", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "mode", "label": "Mode"},
        ]

        form = FormBuilder(fields, on_submit=self.save_receipt)

        data = select("receipt_vouchers", {"company_id": state.company_id})

        columns = [
            {"key": "party_id", "label": "Party"},
            {"key": "amount", "label": "Amount"},
            {"key": "mode", "label": "Mode"},
        ]

        table = TableBuilder(columns, data)

        self.content_area.content = ft.Column([
            form,
            ft.Divider(),
            table
        ])

    def save_receipt(self, data):
        data["company_id"] = state.company_id

        # Insert receipt
        insert("receipt_vouchers", data)

        # Ledger update (credit)
        insert("ledger_entries", {
            "company_id": state.company_id,
            "party_id": data["party_id"],
            "debit": 0,
            "credit": float(data["amount"]),
            "balance": float(data["amount"]) * -1
        })

        self.load_receipts()
        if self.page:
            self.update()

    # =========================================================
    # PAYMENTS
    # =========================================================
    def load_payments(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        fields = [
            {"name": "party_id", "label": "Party ID", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "mode", "label": "Mode"},
        ]

        form = FormBuilder(fields, on_submit=self.save_payment)

        data = select("payment_vouchers", {"company_id": state.company_id})

        columns = [
            {"key": "party_id", "label": "Party"},
            {"key": "amount", "label": "Amount"},
            {"key": "mode", "label": "Mode"},
        ]

        table = TableBuilder(columns, data)

        self.content_area.content = ft.Column([
            form,
            ft.Divider(),
            table
        ])

    def save_payment(self, data):
        data["company_id"] = state.company_id

        # Insert payment
        insert("payment_vouchers", data)

        # Ledger update (credit)
        insert("ledger_entries", {
            "company_id": state.company_id,
            "party_id": data["party_id"],
            "debit": float(data["amount"]),
            "credit": 0,
            "balance": float(data["amount"]) * -1
        })

        self.load_payments()
        self.update()
