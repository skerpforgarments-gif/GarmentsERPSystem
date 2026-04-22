import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select
from components.table import TableBuilder
from components.filters import FilterBar


class ReportsScreen(ft.Container):
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
                ft.Tab(text="Sales"),
                ft.Tab(text="Outstanding"),
                ft.Tab(text="Analytics"),
            ],
        )

        self.content_area = ft.Container(expand=True)

        self.content = ft.Column(
            controls=[
                ft.Text("Business Intelligence & Reports", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                self.tabs,
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                self.content_area
            ],
            expand=True
        )

    def did_mount(self):
        self.load_sales()

    # =========================================================
    # TAB SWITCH
    # =========================================================
    def on_tab_change(self, e):
        index = self.tabs.selected_index

        if index == 0:
            self.load_sales()
        elif index == 1:
            self.load_outstanding()
        elif index == 2:
            self.load_analytics()

        if self.page:
            self.update()

    # =========================================================
    # SALES REPORT
    # =========================================================
    def load_sales(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        filters = [
            {"name": "party_id", "label": "Party"},
        ]

        self.table = TableBuilder([
            {"key": "id", "label": "Order ID"},
            {"key": "party_id", "label": "Party"},
            {"key": "total_amount", "label": "Amount"},
        ])

        filter_bar = FilterBar(filters, on_apply=self.apply_sales_filter)

        self.content_area.content = ft.Column([
            filter_bar,
            ft.Divider(),
            self.table
        ])

        self.apply_sales_filter({})

    def apply_sales_filter(self, filters):
        if not state.company_id:
            return
            
        query = {"company_id": state.company_id}

        if filters.get("party_id"):
            query["party_id"] = filters["party_id"]

        data = select("orders", query)
        self.table.set_data(data)

    # =========================================================
    # OUTSTANDING REPORT
    # =========================================================
    def load_outstanding(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        data = select("ledger_entries", {"company_id": state.company_id})

        columns = [
            {"key": "party_id", "label": "Party"},
            {"key": "debit", "label": "Debit"},
            {"key": "credit", "label": "Credit"},
        ]

        table = TableBuilder(columns, data)

        self.content_area.content = table

    # =========================================================
    # ANALYTICS
    # =========================================================
    def load_analytics(self):
        if not state.company_id:
            self.content_area.content = ft.Text("Select company first")
            return

        orders = select("orders", {"company_id": state.company_id})

        total_sales = sum(o.get("total_amount", 0) for o in orders)
        total_orders = len(orders)

        self.content_area.content = ft.Row([
            self.build_card("Total Sales", f"₹{round(total_sales, 2)}"),
            self.build_card("Total Orders", str(total_orders)),
        ])

    # =========================================================
    # CARD
    # =========================================================
    def build_card(self, title, value):
        return ft.Container(
            expand=True,
            padding=24,
            bgcolor=AppColors.BG_CARD,
            border_radius=AppStyles.RADIUS,
            shadow=AppStyles.CARD_SHADOW,
            border=ft.border.all(1, "#F0F0F0"),
            content=ft.Column([
                ft.Text(title.upper(), size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                ft.Text(value, size=AppStyles.H2_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
            ], spacing=5)
        )
