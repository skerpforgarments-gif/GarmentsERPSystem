import flet as ft
from datetime import date
from core.state import state
from core.theme import AppColors, AppStyles
from database.db import select, insert

class ProductionEntryTab(ft.Column):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.spacing = 20
        
        S = AppStyles.get_input_style()
        self.entry_date = ft.TextField(label="Entry Date", width=150, value=date.today().isoformat(), **S)
        self.ref_no = ft.TextField(label="Reference / Batch No", width=200, **S)
        self.item_dd = ft.Dropdown(label="Select Item (Finished Goods)", width=300, on_change=self.on_item_change, **S)
        
        self.sizes_grid = ft.Row(wrap=True, spacing=15)
        self.size_inputs = {}
        
        self.controls = [
            ft.Container(
                bgcolor=ft.colors.WHITE, padding=20, border_radius=8, border=ft.border.all(1, "#E2E8F0"),
                content=ft.Column([
                    ft.Text("Production / Stock Entry", size=18, weight="bold", color=AppColors.PRIMARY),
                    ft.Text("Add manufactured goods directly into the warehouse.", size=12, color=AppColors.TEXT_SUB),
                    ft.Divider(height=10, color="transparent"),
                    ft.Row([self.entry_date, self.ref_no, self.item_dd], spacing=15, wrap=True)
                ])
            ),
            ft.Container(
                bgcolor=ft.colors.WHITE, padding=20, border_radius=8, border=ft.border.all(1, "#E2E8F0"), expand=True,
                content=ft.Column([
                    ft.Text("Enter Produced Quantities by Size", size=14, weight="bold"),
                    self.sizes_grid,
                    ft.Container(expand=True),
                    ft.Divider(height=1, color="#E2E8F0"),
                    ft.Row([
                        ft.ElevatedButton("Save Production Entry", icon=ft.icons.SAVE, on_click=self.save_entry, style=AppStyles.primary_button_style())
                    ], alignment=ft.MainAxisAlignment.END)
                ])
            )
        ]
        
    def did_mount(self):
        if not state.company_id: return
        items = select("items", {"company_id": state.company_id})
        # Filter items if needed (e.g. item_type == 'Sales' or 'Both')
        items = [i for i in items if i.get("item_type") in ("Sales", "Both")]
        self.item_dd.options = [ft.dropdown.Option(key=str(i["id"]), text=f"{i['item_name']} ({i.get('item_code','')})") for i in items]
        if self.page: self.update()

    def on_item_change(self, e):
        try:
            item_id = self.item_dd.value
            if not item_id: return
            
            item_data = select("items", {"id": item_id})
            
            self.sizes_grid.controls.clear()
            self.size_inputs.clear()
            
            if not item_data:
                self._snack("Item not found in DB", "orange")
                self.update()
                return
                
            sizes = item_data[0].get("sizes")
            if sizes is None:
                sizes = []
            elif isinstance(sizes, str):
                import json
                try: sizes = json.loads(sizes)
                except: sizes = []
                
            if not sizes:
                self._snack("No sizes found for this item.", "orange")
            else:
                for s in sizes:
                    tf = ft.TextField(label="Qty", width=100, value="0", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER, dense=True)
                    self.size_inputs[s] = tf
                    self.sizes_grid.controls.append(
                        ft.Container(
                            padding=10, bgcolor="#F8FAFC", border_radius=8, border=ft.border.all(1, "#E2E8F0"),
                            content=ft.Column([
                                ft.Text(str(s), weight="bold", size=14, color=AppColors.PRIMARY),
                                tf
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                    )
            self.sizes_grid.update()
            self.update()
        except Exception as ex:
            self._snack(f"Error in dropdown: {ex}", "red")

    def save_entry(self, e):
        if not self.item_dd.value:
            self._snack("Please select an item", "red")
            return
            
        added_any = False
        item_id = self.item_dd.value
        d = self.entry_date.value
        r = self.ref_no.value or "Manual Entry"
        
        for sz, tf in self.size_inputs.items():
            qty = int(float(tf.value or 0))
            if qty > 0:
                insert("stock_ledger", {
                    "company_id": state.company_id,
                    "entry_date": d,
                    "item_id": item_id,
                    "size_value": sz,
                    "transaction_type": "IN",
                    "ref_type": "Production",
                    "ref_id": r,
                    "qty": qty,
                    "rate": 0  # Production cost logic can be added later
                })
                added_any = True
                
        if added_any:
            self._snack("✅ Stock successfully added to warehouse!", "green")
            self.ref_no.value = ""
            self.item_dd.value = None
            self.sizes_grid.controls.clear()
            self.size_inputs.clear()
            if self.page: self.update()
        else:
            self._snack("No quantities entered", "orange")

    def _snack(self, msg, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

class InventoryScreen(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 10
        self.prod_tab = ProductionEntryTab()
        self.content = ft.Column([
            ft.Tabs(selected_index=0, expand=True, tabs=[ft.Tab(text="Production Entry", content=self.prod_tab)])
        ], expand=True)

    def did_mount(self):
        self.prod_tab.did_mount()
