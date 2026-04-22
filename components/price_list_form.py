import flet as ft
from datetime import datetime
from core.theme import AppColors, AppStyles

class PriceListForm(ft.Container):
    def __init__(self, on_submit=None):
        super().__init__()
        self.expand = True
        self.padding = 10
        self.on_submit = on_submit
        
        self.all_items = []

        # =============================================
        # HEADER FIELDS
        # =============================================
        self.style_args = {
            "dense": True,
            "text_size": 13,
            "height": 45,
            "border_radius": AppStyles.BUTTON_RADIUS,
            "border_color": "#E2E8F0",
            "focused_border_color": AppColors.PRIMARY,
            "bgcolor": "#F8FAFC",
            "label_style": ft.TextStyle(color=AppColors.TEXT_SUB, size=12)
        }

        self.list_name = ft.TextField(label="Price List Name *", width=250, **self.style_args)
        self.effective_date = ft.TextField(
            label="Effective Date (YYYY-MM-DD) *", width=200,
            value=datetime.now().strftime("%Y-%m-%d"), **self.style_args
        )
        self.price_type = ft.Dropdown(
            label="Primary Price Type", width=160,
            value="Wholesale",
            options=[
                ft.dropdown.Option("Wholesale"),
                ft.dropdown.Option("Retail"),
                ft.dropdown.Option("MRP"),
            ], **self.style_args
        )

        # =============================================
        # ITEM SELECTION
        # =============================================
        self.item_dd = ft.Dropdown(
            label="Select Item to Setup Pricing", width=350,
            on_change=self.on_item_select, **self.style_args
        )

        # =============================================
        # SIZE MATRIX (Dynamic per Item)
        # =============================================
        self.rate_inputs = {}  # {size: {"wholesale": TextField, "retail": TextField, "mrp": TextField}}
        self.matrix_grid = ft.Row(wrap=True, spacing=10)
        self.matrix_section = ft.Container(
            content=ft.Column([
                ft.Text("ITEM SIZE PRICING", weight="bold", size=10, color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                self.matrix_grid
            ], spacing=8),
            visible=False,
            padding=15,
            border=ft.border.all(1, "#F1F5F9"),
            border_radius=AppStyles.RADIUS,
            bgcolor="#F8FAFC"
        )
        
        # We need a way to store multiple items' prices before submitting, 
        # or we assume we edit ONE item's pricing per submission?
        # Actually, a Price List typically holds many items. 
        # To keep UI simple, let's allow editing existing rates by just selecting an item and updating the matrix.
        # But for submission, we want to return the structured dictionary of everything filled out.
        # So we'll maintain a state of `self.item_prices_state = {item_id: {size: {rates...}}}`
        self.item_prices_state = {}

        # =============================================
        # BUTTONS
        # =============================================
        save_btn = ft.ElevatedButton(
            "Save", icon=ft.icons.SAVE, on_click=self._submit,
            style=AppStyles.primary_button_style(), height=45
        )
        save_as_btn = ft.ElevatedButton(
            "Save As", icon=ft.icons.COPY, on_click=self._save_as,
            style=ft.ButtonStyle(
                bgcolor=AppColors.WARNING, color=ft.colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppStyles.BUTTON_RADIUS)
            ), height=45
        )
        clear_btn = ft.TextButton(
            "Clear", icon=ft.icons.REFRESH, on_click=self.clear,
            style=AppStyles.secondary_button_style()
        )

        # =============================================
        # LAYOUT
        # =============================================
        self.content = ft.Column(
            controls=[
                ft.Row([self.list_name, self.effective_date, self.price_type], spacing=12, wrap=True),
                ft.Divider(height=1, color="grey300"),
                ft.Row([self.item_dd], spacing=12, wrap=True),
                self.matrix_section,
                ft.Row([save_btn, save_as_btn, clear_btn], spacing=12, wrap=True),
            ],
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

    def load_metadata(self, items):
        """Loads items for the dropdown. items should be a list of dicts."""
        self.all_items = items
        self.item_dd.options.clear()
        
        for item in self.all_items:
            label = f"{item.get('item_name')} ({item.get('item_code')})"
            self.item_dd.options.append(ft.dropdown.Option(key=str(item.get("id")), text=label))
            
        try:
            self.update()
        except Exception:
            pass

    def on_item_select(self, e):
        """When an item is selected, render the size grid for it."""
        item_id = self.item_dd.value
        if not item_id:
            self.matrix_section.visible = False
            self.update()
            return
            
        # Optional: Save current matrix state to state dict before switching
        # Let's skip auto-saving on switch for now to keep it simple, 
        # or we could save it so users can configure multiple items then Save.
        # Doing multiple items before saving is best. Let's auto-save current grid if populated.
        
        item = next((i for i in self.all_items if str(i.get("id")) == item_id), None)
        if not item:
            return
            
        sizes = item.get("sizes", [])
        
        self.rate_inputs.clear()
        self.matrix_grid.controls.clear()
        
        existing_rates = self.item_prices_state.get(item_id, {})
        
        if not sizes:
            self.matrix_grid.controls.append(ft.Text("No sizes configured for this item.", color="red"))
        else:
            for s in sizes:
                s_rates = existing_rates.get(s, {})
                ws = ft.TextField(label="Wholesale", value=str(s_rates.get("wholesale_rate", 0)), width=85, **self.style_args, text_align=ft.TextAlign.RIGHT, keyboard_type=ft.KeyboardType.NUMBER)
                rt = ft.TextField(label="Retail", value=str(s_rates.get("retail_rate", 0)), width=85, **self.style_args, text_align=ft.TextAlign.RIGHT, keyboard_type=ft.KeyboardType.NUMBER)
                mrp = ft.TextField(label="MRP", value=str(s_rates.get("mrp_rate", 0)), width=85, **self.style_args, text_align=ft.TextAlign.RIGHT, keyboard_type=ft.KeyboardType.NUMBER)
                
                self.rate_inputs[s] = {"wholesale": ws, "retail": rt, "mrp": mrp}
                
                self.matrix_grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(s, size=11, weight="bold", color=AppColors.TEXT_HEADER),
                            ws, rt, mrp
                        ], spacing=7, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=12,
                        bgcolor=AppColors.BG_CARD,
                        border_radius=8,
                        shadow=AppStyles.CARD_SHADOW,
                        border=ft.border.all(1, "#F0F0F0")
                    )
                )
                
        self.matrix_section.visible = True
        try:
            self.update()
        except:
            pass
            
    def _save_current_grid_to_state(self):
        """Forces the current UI table inputs onto the Python state dict"""
        item_id = self.item_dd.value
        if not item_id or not self.matrix_section.visible:
            return
            
        size_dict = {}
        for s, inputs in self.rate_inputs.items():
            try:
                ws = float(inputs["wholesale"].value or 0)
                rt = float(inputs["retail"].value or 0)
                mrp = float(inputs["mrp"].value or 0)
            except ValueError:
                ws = rt = mrp = 0.0
                
            size_dict[s] = {
                "wholesale_rate": ws,
                "retail_rate": rt,
                "mrp_rate": mrp
            }
            
        self.item_prices_state[item_id] = size_dict

    def get_values(self):
        self._save_current_grid_to_state() # Flush current active grid
        
        return {
            "list_name": self.list_name.value or "",
            "effective_date": self.effective_date.value or "",
            "price_type": self.price_type.value or "Wholesale",
            "items_pricing": self.item_prices_state
        }

    def set_values(self, data: dict, items_pricing: dict = None):
        self.list_name.value = data.get("list_name", "")
        if data.get("effective_date"):
            self.effective_date.value = str(data.get("effective_date"))
        self.price_type.value = data.get("price_type", "Wholesale")
        
        self.item_prices_state = items_pricing or {}
        self.item_dd.value = None
        self.matrix_section.visible = False
        
        try:
            self.update()
        except:
            pass

    def clear(self, e=None):
        self.list_name.value = ""
        self.effective_date.value = datetime.now().strftime("%Y-%m-%d")
        self.price_type.value = "Wholesale"
        self.item_prices_state = {}
        self.item_dd.value = None
        self.matrix_section.visible = False
        self.list_name.error_text = None
        try:
            self.update()
        except:
            pass

    def _save_as(self, e):
        if not self.list_name.value:
            self.list_name.error_text = "Enter a NEW name for cloning"
            self.update()
            return
        self.list_name.error_text = None
        self._save_current_grid_to_state()
        
        # We pass a flag to tell the parent that this is a CLONE (ignore edit_id)
        if self.on_submit:
            data = self.get_values()
            data["is_clone"] = True
            self.on_submit(data)

    def _submit(self, e):
        if not self.list_name.value:
            self.list_name.error_text = "Required"
            self.update()
            return
        self.list_name.error_text = None
        self._save_current_grid_to_state()
        
        if self.on_submit:
            self.on_submit(self.get_values())
