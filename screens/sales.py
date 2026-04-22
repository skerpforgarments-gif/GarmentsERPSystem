import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import insert, select


class SalesScreen(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.padding = 10

        # =========================
        # HEADER
        # =========================
        style_args = {
            "dense": True,
            "text_size": 13,
            "height": 45,
            "border_radius": AppStyles.BUTTON_RADIUS,
            "border_color": "#E2E8F0",
            "focused_border_color": AppColors.PRIMARY,
            "bgcolor": "#F8FAFC",
            "label_style": ft.TextStyle(color=AppColors.TEXT_SUB, size=12)
        }

        self.party_field = ft.TextField(label="Select Party", width=300, **style_args)

        self.add_item_btn = ft.TextButton(
            "Add New Item Row", 
            icon=ft.icons.ADD_CIRCLE_OUTLINE, 
            on_click=self.add_row,
            style=AppStyles.secondary_button_style()
        )

        # =========================
        # TABLE (ITEMS)
        # =========================
        self.rows = []

        self.table = ft.Column()

        # =========================
        # TOTAL
        # =========================
        self.total_text = ft.Text("Total: ₹0", size=AppStyles.H2_SIZE, weight="bold", color=AppColors.PRIMARY)

        # =========================
        # SAVE BUTTON
        # =========================
        self.save_btn = ft.ElevatedButton(
            "Place Order", 
            icon=ft.icons.SHOPPING_CART_CHECKOUT, 
            on_click=self.save_order,
            style=AppStyles.primary_button_style(),
            height=50
        )

        # =========================
        # LAYOUT
        # =========================
        self.content = ft.Column(
            controls=[
                ft.Text("Sales Order Processing", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("ORDER DETAILS", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                        ft.Row([self.party_field, ft.Container(expand=True), self.add_item_btn]),
                        ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                        self.table,
                        ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                        ft.Row([
                            ft.Container(expand=True),
                            self.total_text
                        ]),
                        ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                        ft.Row([
                            ft.Container(expand=True),
                            self.save_btn
                        ])
                    ], spacing=10),
                    padding=24,
                    bgcolor=AppColors.BG_CARD,
                    border_radius=AppStyles.RADIUS,
                    shadow=AppStyles.CARD_SHADOW,
                    border=ft.border.all(1, "#F0F0F0")
                )
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )

    def did_mount(self):
        self.add_row()

    # =========================================================
    # ADD ROW
    # =========================================================
    def add_row(self, e=None):
        style_args = {
            "dense": True,
            "text_size": 13,
            "height": 45,
            "border_radius": AppStyles.BUTTON_RADIUS,
            "border_color": "#E2E8F0",
            "focused_border_color": AppColors.PRIMARY,
            "bgcolor": "#F8FAFC",
        }
        item_field = ft.TextField(label="Item", expand=True, **style_args)
        qty_field = ft.TextField(label="Qty", width=120, **style_args)
        rate_field = ft.TextField(label="Rate", width=120, **style_args)

        row = {
            "item": item_field,
            "qty": qty_field,
            "rate": rate_field
        }

        self.rows.append(row)

        self.table.controls.append(
            ft.Row([item_field, qty_field, rate_field])
        )

        if self.page:
            self.update()

    # =========================================================
    # CALCULATE TOTAL
    # =========================================================
    def calculate_total(self):
        total = 0

        for r in self.rows:
            try:
                qty = float(r["qty"].value or 0)
                rate = float(r["rate"].value or 0)
                total += qty * rate
            except:
                pass

        return total

    # =========================================================
    # SAVE ORDER
    # =========================================================
    def save_order(self, e):
        if not state.company_id:
            print("Select company first")
            return

        party_id = self.party_field.value

        if not party_id:
            print("Party required")
            return

        total = self.calculate_total()

        # -------------------------
        # INSERT ORDER
        # -------------------------
        order = insert("orders", {
            "company_id": state.company_id,
            "party_id": party_id,
            "total_amount": total
        })

        order_id = order[0]["id"]

        # -------------------------
        # INSERT ITEMS
        # -------------------------
        for r in self.rows:
            insert("order_items", {
                "order_id": order_id,
                "item_id": r["item"].value,
                "qty_pcs": int(r["qty"].value or 0),
                "rate": float(r["rate"].value or 0),
                "amount": float(r["qty"].value or 0) * float(r["rate"].value or 0)
            })

        # -------------------------
        # LEDGER ENTRY (DEBIT)
        # -------------------------
        from datetime import date
        insert("ledger_entries", {
            "company_id": state.company_id,
            "party_id": party_id,
            "ref_type": "sales_order",
            "ref_id": str(order_id),
            "debit": total,
            "credit": 0,
            "date": date.today().isoformat()
        })

        # -------------------------
        # RESET UI
        # -------------------------
        self.rows.clear()
        self.table.controls.clear()
        self.add_row()

        self.total_text.value = "Total: ₹0"

        self.update()
