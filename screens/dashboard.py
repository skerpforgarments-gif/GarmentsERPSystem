import flet as ft
from datetime import datetime, timezone

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, select_recent


class DashboardScreen(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.padding = 20

        # =========================
        # UI ELEMENTS
        # =========================
        self.company_text = ft.Text("", size=16, color=ft.colors.BLUE_GREY_400, weight="w500")
        self.header_text = ft.Text("Business Overview", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER)
        
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

        # Activity list (will be populated dynamically)
        self.activity_col = ft.Column([], spacing=12)
        self.activity_loading = ft.ProgressRing(width=24, height=24, stroke_width=2, visible=False)

        # =========================
        # LAYOUT
        # =========================
        self.content = ft.Column(
            controls=[
                # Header
                ft.Row([
                    ft.Column([
                        self.header_text,
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

                # Recent Activity Section (Dynamic)
                ft.Row([
                    ft.Text("Recent Activity", size=18, weight="bold", color=AppColors.TEXT_HEADER),
                    self.activity_loading,
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.icons.REFRESH_ROUNDED, 
                        icon_color=AppColors.PRIMARY, 
                        icon_size=20,
                        tooltip="Refresh Activity",
                        on_click=lambda _: self.load_data()
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    expand=True,
                    padding=24,
                    bgcolor=AppColors.BG_CARD,
                    border_radius=AppStyles.RADIUS,
                    shadow=AppStyles.CARD_SHADOW,
                    border=ft.border.all(1, "#F0F0F0"),
                    content=self.activity_col
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
    # BUILD ACTIVITY ITEM (Enhanced with type-specific icons)
    # =========================================================
    def build_activity_item(self, title, subtitle, time_str, icon=ft.icons.NOTIFICATIONS_OUTLINED, accent=None):
        accent = accent or AppColors.PRIMARY
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=8,
            bgcolor=ft.colors.with_opacity(0.02, accent),
            border=ft.border.all(1, ft.colors.with_opacity(0.06, accent)),
            content=ft.Row([
                ft.Container(
                    width=40, height=40, 
                    bgcolor=ft.colors.with_opacity(0.1, accent), 
                    border_radius=20,
                    content=ft.Icon(icon, color=accent, size=18)
                ),
                ft.Column([
                    ft.Text(title, size=14, weight="bold", color=AppColors.TEXT_HEADER),
                    ft.Text(subtitle, size=12, color=AppColors.TEXT_SUB),
                ], spacing=2, expand=True),
                ft.Text(time_str, size=11, color=AppColors.TEXT_MUTED)
            ], alignment=ft.MainAxisAlignment.START, spacing=15)
        )

    # =========================================================
    # RELATIVE TIME HELPER
    # =========================================================
    @staticmethod
    def _relative_time(timestamp_str):
        """Convert an ISO timestamp string to a human-friendly relative time."""
        if not timestamp_str:
            return ""
        try:
            # Parse ISO format (handles both Z and +00:00 suffixes)
            ts = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            diff = now - dt

            seconds = int(diff.total_seconds())
            if seconds < 0:
                return "just now"
            if seconds < 60:
                return "just now"
            minutes = seconds // 60
            if minutes < 60:
                return f"{minutes}m ago"
            hours = minutes // 60
            if hours < 24:
                return f"{hours}h ago"
            days = hours // 24
            if days < 7:
                return f"{days}d ago"
            if days < 30:
                weeks = days // 7
                return f"{weeks}w ago"
            return dt.strftime("%d %b %Y")
        except Exception:
            return str(timestamp_str)[:10]

    # =========================================================
    # LOAD DATA
    # =========================================================
    def load_data(self):
        if not state.company_id:
            self.header_text.value = "Business Overview"
            self.company_text.value = "Welcome back! Please select a company."
            if self.page: self.update()
            return

        company_name = state.current_company.get('name', 'Business')
        self.header_text.value = "Business Overview"
        self.company_text.value = f"Managing: {company_name}"

        # Show loading spinner
        self.activity_loading.visible = True
        if self.page: self.update()

        try:
            # ── Stat cards ─────────────────────────────
            orders = select("orders", {"company_id": state.company_id})
            total_orders = len(orders)
            total_sales = sum(o.get("total_amount", 0) for o in orders)

            ledger = select("ledger_entries", {"company_id": state.company_id})
            outstanding = sum(l.get("balance", 0) for l in ledger)

            self.sales_card.value_text.value = f"₹{round(total_sales, 2):,}"
            self.orders_card.value_text.value = str(total_orders)
            self.outstanding_card.value_text.value = f"₹{round(outstanding, 2):,}"

        except Exception as e:
            print("Dashboard stats error:", e)

        # ── Recent Activity (Dynamic) ──────────────
        try:
            activity_items = []
            company_filter = {"company_id": state.company_id}

            # 1. Recent Orders
            recent_orders = select_recent("orders", company_filter, order_by="created_at", limit=5)
            party_ids = list(set(str(o.get("party_id", "")) for o in recent_orders if o.get("party_id")))
            party_map = {}
            if party_ids:
                all_parties = select("parties", {"company_id": state.company_id})
                party_map = {str(p["id"]): p["name"] for p in all_parties}

            for o in recent_orders:
                p_name = party_map.get(str(o.get("party_id", "")), "Unknown Party")
                amount = o.get("net_amount") or o.get("total_amount") or 0
                status = o.get("status", "Pending")
                activity_items.append({
                    "title": f"Order {o.get('order_no', '—')} — {p_name}",
                    "subtitle": f"₹{float(amount):,.2f} · {status}",
                    "time": o.get("created_at", ""),
                    "icon": ft.icons.SHOPPING_BAG_OUTLINED,
                    "accent": AppColors.INFO,
                })

            # 2. Recent Packing Slips
            try:
                recent_slips = select_recent("packing_slips", company_filter, order_by="created_at", limit=3)
                for s in recent_slips:
                    p_name = party_map.get(str(s.get("party_id", "")), "Unknown Party")
                    activity_items.append({
                        "title": f"Packing Slip {s.get('slip_no', '—')} — {p_name}",
                        "subtitle": f"Pcs: {s.get('total_pcs', 0)} · Status: {s.get('status', 'Packed')}",
                        "time": s.get("created_at", ""),
                        "icon": ft.icons.INVENTORY_2_OUTLINED,
                        "accent": "#8B5CF6",
                    })
            except Exception:
                pass  # Table may not exist yet

            # 3. Recent Final Invoices
            try:
                recent_invoices = select_recent("final_invoices", company_filter, order_by="created_at", limit=3)
                for inv in recent_invoices:
                    p_name = party_map.get(str(inv.get("party_id", "")), "Unknown Party")
                    amt = inv.get("net_amount") or inv.get("total_amount") or 0
                    activity_items.append({
                        "title": f"Invoice {inv.get('invoice_no', '—')} — {p_name}",
                        "subtitle": f"₹{float(amt):,.2f} · Sales Invoice",
                        "time": inv.get("created_at", ""),
                        "icon": ft.icons.RECEIPT_LONG_OUTLINED,
                        "accent": "#059669",
                    })
            except Exception:
                pass

            # 4. Recent Vouchers (Receipts)
            try:
                recent_receipts = select_recent("receipt_vouchers", company_filter, order_by="created_at", limit=3)
                for v in recent_receipts:
                    p_name = party_map.get(str(v.get("party_id", "")), "Unknown Party")
                    activity_items.append({
                        "title": f"Receipt Voucher — {p_name}",
                        "subtitle": f"₹{float(v.get('amount', 0)):,.2f} · {v.get('mode', 'Cash')}",
                        "time": v.get("created_at", ""),
                        "icon": ft.icons.PAYMENTS_OUTLINED,
                        "accent": "#D97706",
                    })
            except Exception:
                pass

            # 5. Recently added Parties
            try:
                recent_parties = select_recent("parties", company_filter, order_by="created_at", limit=2)
                for p in recent_parties:
                    activity_items.append({
                        "title": f"New Party: {p.get('name', '—')}",
                        "subtitle": f"City: {p.get('city', '—')} · {p.get('party_type', 'Customer')}",
                        "time": p.get("created_at", ""),
                        "icon": ft.icons.PERSON_ADD_ALT_1_OUTLINED,
                        "accent": "#7C3AED",
                    })
            except Exception:
                pass

            # 6. Recently added Items
            try:
                recent_items = select_recent("items", company_filter, order_by="created_at", limit=2)
                for it in recent_items:
                    activity_items.append({
                        "title": f"New Item: {it.get('item_name', '—')}",
                        "subtitle": f"Code: {it.get('item_code', '—')} · {it.get('category', 'General')}",
                        "time": it.get("created_at", ""),
                        "icon": ft.icons.CHECKROOM_OUTLINED,
                        "accent": "#0891B2",
                    })
            except Exception:
                pass

            # ── Sort all activity by timestamp (newest first) ──
            def sort_key(item):
                ts = item.get("time", "")
                if not ts:
                    return ""
                return ts

            activity_items.sort(key=sort_key, reverse=True)

            # Limit to top 10 combined
            activity_items = activity_items[:10]

            # Build UI
            self.activity_col.controls.clear()
            if not activity_items:
                self.activity_col.controls.append(
                    ft.Container(
                        padding=40,
                        content=ft.Column([
                            ft.Icon(ft.icons.INBOX_OUTLINED, size=48, color=AppColors.TEXT_MUTED),
                            ft.Text("No recent activity yet", size=14, color=AppColors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                            ft.Text("Start by creating orders, parties, or items", size=12, color=AppColors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                    )
                )
            else:
                for item in activity_items:
                    self.activity_col.controls.append(
                        self.build_activity_item(
                            item["title"],
                            item["subtitle"],
                            self._relative_time(item["time"]),
                            icon=item.get("icon", ft.icons.NOTIFICATIONS_OUTLINED),
                            accent=item.get("accent", AppColors.PRIMARY),
                        )
                    )

        except Exception as e:
            print("Dashboard activity error:", e)
            self.activity_col.controls = [
                ft.Text(f"Could not load activity: {e}", size=12, color=AppColors.DANGER)
            ]

        # Hide loading
        self.activity_loading.visible = False
        if self.page: self.update()

    def on_state_change(self, updated_state):
        self.load_data()

    def did_unmount(self):
        state.unsubscribe(self.on_state_change)

