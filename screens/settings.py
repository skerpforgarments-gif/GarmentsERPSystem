import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.db import insert, select


class SettingsScreen(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.padding = 10

        # =========================
        # FORM (CREATE COMPANY)
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

        self.company_name = ft.TextField(label="Company Name", width=400, **style_args)

        self.create_btn = ft.ElevatedButton(
            "Create New Business Profile",
            on_click=self.handle_create_company,
            style=AppStyles.primary_button_style(),
            height=45
        )

        # =========================
        # COMPANY LIST
        # =========================
        self.company_dropdown = ft.Dropdown(
            label="Switch Workspace",
            width=400,
            on_change=self.select_company,
            **style_args
        )

        self.current_company_text = ft.Text("No active workspace selected", size=14, color=AppColors.TEXT_SUB)

        # =========================
        # LAYOUT
        # =========================
        self.content = ft.Column(
            controls=[
                ft.Text("Platform Settings", size=AppStyles.H1_SIZE, weight="bold", color=AppColors.TEXT_HEADER),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("BUSINESS SETUP", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                        ft.Text("Initialize a new company profile to manage multiple divisions.", size=13, color=AppColors.TEXT_SUB),
                        ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                        self.company_name,
                        self.create_btn,
                    ], spacing=10),
                    padding=24,
                    bgcolor=AppColors.BG_CARD,
                    border_radius=AppStyles.RADIUS,
                    shadow=AppStyles.CARD_SHADOW,
                    border=ft.border.all(1, "#F0F0F0")
                ),
                
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("WORKSPACE MANAGEMENT", size=10, weight="bold", color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                        ft.Text("Switch between your authorized business entities.", size=13, color=AppColors.TEXT_SUB),
                        ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                        self.company_dropdown,
                        ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                        ft.Row([
                            ft.Text("ACTIVE ENTITY:", weight="bold", size=12, color=AppColors.TEXT_HEADER),
                            self.current_company_text,
                        ], spacing=10)
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
        # Auth Guard
        if not state.current_user:
            return
        # Load companies
        self.load_companies()

    # =========================================================
    # LOAD COMPANIES
    # =========================================================
    def load_companies(self):
        try:
            companies = select("companies")

            self.company_dropdown.options = [
                ft.dropdown.Option(
                    key=str(c["id"]),
                    text=c["name"]
                )
                for c in companies
            ]

        except Exception as e:
            print("Error loading companies:", e)

        if self.page:
            self.update()

    def handle_create_company(self, e):
        name = self.company_name.value

        if not name:
            print("Company name required (ignored if startup noise)")
            return

        try:
            insert("companies", {
                "name": name,
                "user_id": state.current_user.id
            })

            self.company_name.value = ""
            self.load_companies()

        except Exception as e:
            print("Error creating company:", e)

        if self.page:
            self.update()

    # =========================================================
    # SELECT COMPANY
    # =========================================================
    def select_company(self, e):
        company_id = self.company_dropdown.value # UUID is a string

        try:
            companies = select("companies")
            company = next(c for c in companies if str(c["id"]) == company_id)

            state.set_company(company)

            self.current_company_text.value = company["name"]

        except Exception as e:
            print("Error selecting company:", e)

        if self.page:
            self.update()
