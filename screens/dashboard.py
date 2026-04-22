import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select


class DashboardScreen(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.padding = 20

        # =========================
        # UI ELEMENTS
        # =========================
        self.company_text = ft.Text("", size=16, color=ft.colors.BLUE_GREY_400, weight="w500")
        
        # Premium Cards (Updated design)
        self.sales_card = self.build_stat_card(
            "Total Sales", "₹0", ft.icons.MONETIZATION_ON, 
            AppColors.PRIMARY, "+12%"
        )
        self.orders_card = self.build_stat_card(
            "Total Orders", "0", ft.icons.SHOPPING_BAG, 
            AppColors.INFO, "+5%"
        )
        self.outstanding_card = self.build_stat_card(
            "Account O/S", "₹0", ft.icons.ACCOUNT_BALANCE, 
            AppColors.DANGER, "-2%"
        )

        # =========================
        # LAYOUT
        # =========================
        self.content = ft.Column(
            controls=[
                # Header
                ft.Row([
                    ft.Column([
                        ft.Text("Business Overview", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                        self.company_text,
                    ], spacing=2),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(height=20, color=ft.colors.TRANSPARENT),

                # Stats Grid
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(self.sales_card, col={"sm": 12, "md": 4}),
                        ft.Container(self.orders_card, col={"sm": 12, "md": 4}),
                        ft.Container(self.outstanding_card, col={"sm": 12, "md": 4}),
                    ],
                    spacing=20
                ),

                ft.Divider(height=30, color=ft.colors.TRANSPARENT),

                # Bottom Section (Recent Activity Mockup)
                ft.Text("Recent Activity", size=18, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Container(
                    expand=True,
                    padding=24,
                    bgcolor=AppColors.BG_CARD,
                    border_radius=AppStyles.RADIUS,
                    shadow=AppStyles.CARD_SHADOW,
                    border=ft.border.all(1, "#F0F0F0"),
                    content=ft.Column([
                        self.build_activity_item("Order #1024 - Global Traders", "Pending Packing", "2 mins ago"),
                        self.build_activity_item("Price List Updated: Summer 2024", "System Update", "1 hour ago"),
                        self.build_activity_item("New Party Added: Tirupur Exports", "Admin Action", "5 hours ago"),
                    ], spacing=15)
                )
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO
        )

        state.subscribe(self.on_state_change)

    def did_mount(self):
        if not state.current_user:
            return
        self.load_data()

    # =========================================================
    # BUILD STAT CARD
    # =========================================================
    def build_stat_card(self, title, value, icon, accent_color, grow_text):
        value_text = ft.Text(value, size=24, weight="bold", color=AppColors.TEXT_HEADER)
        
        card = ft.Container(
            padding=24,
            bgcolor=AppColors.BG_CARD,
            border_radius=AppStyles.RADIUS,
            shadow=AppStyles.CARD_SHADOW,
            border=ft.border.all(1, "#F0F0F0"),
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(icon, color=accent_color, size=20),
                            bgcolor=ft.colors.with_opacity(0.1, accent_color),
                            padding=10,
                            border_radius=10
                        ),
                        ft.Container(
                            content=ft.Text(grow_text, size=11, weight="bold", color=accent_color),
                            bgcolor=ft.colors.with_opacity(0.1, accent_color),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=15
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                    ft.Text(title, size=13, color=AppColors.TEXT_SUB, weight="w500"),
                    value_text
                ],
                spacing=0
            )
        )
        card.value_text = value_text
        return card

    # =========================================================
    # BUILD ACTIVITY ITEM
    # =========================================================
    def build_activity_item(self, title, subtitle, time):
        return ft.Row([
            ft.Container(
                width=40, height=40, 
                bgcolor=AppColors.PRIMARY_LIGHT, 
                border_radius=20,
                content=ft.Icon(ft.icons.NOTIFICATIONS_OUTLINED, color=AppColors.PRIMARY, size=18)
            ),
            ft.Column([
                ft.Text(title, size=14, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Text(subtitle, size=12, color=AppColors.TEXT_SUB),
            ], spacing=0, expand=True),
            ft.Text(time, size=11, color=AppColors.TEXT_MUTED)
        ], alignment=ft.MainAxisAlignment.START, spacing=15)

    # =========================================================
    # LOAD DATA
    # =========================================================
    def load_data(self):
        if not state.company_id:
            self.company_text.value = "Welcome back! Please select a company."
            if self.page: self.update()
            return

        self.company_text.value = f"Managing: {state.current_company.get('name')}"

        try:
            orders = select("orders", {"company_id": state.company_id})
            total_orders = len(orders)
            total_sales = sum(o.get("total_amount", 0) for o in orders)

            ledger = select("ledger_entries", {"company_id": state.company_id})
            outstanding = sum(l.get("balance", 0) for l in ledger)

            self.sales_card.value_text.value = f"₹{round(total_sales, 2)}"
            self.orders_card.value_text.value = str(total_orders)
            self.outstanding_card.value_text.value = f"₹{round(outstanding, 2)}"

        except Exception as e:
            print("Dashboard error:", e)

        if self.page: self.update()

    def on_state_change(self, updated_state):
        self.load_data()

    def did_unmount(self):
        state.unsubscribe(self.on_state_change)
