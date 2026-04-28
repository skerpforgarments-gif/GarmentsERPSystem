import flet as ft
from core.theme import AppColors, AppStyles
from database.db import select

# Canonical size order for Tirupur garments
_ALPHA_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "4XL", "5XL"]

def _size_sort_key(s: str):
    """Return a sort key so sizes appear in natural order."""
    s = str(s).strip()
    if s.isdigit():
        return (0, int(s), s)          # numeric sizes: 28, 30, 32 …
    if s.upper() in _ALPHA_ORDER:
        return (1, _ALPHA_ORDER.index(s.upper()), s)  # alpha sizes: S M L …
    return (2, 0, s)                   # anything else: alphabetical

def sort_sizes(sizes):
    return sorted(sizes, key=_size_sort_key)

class SizeMatrixModal(ft.AlertDialog):
    def __init__(self, on_submit):
        super().__init__()
        self.on_submit = on_submit
        self.modal = True
        self.title = ft.Text("Select Item & Sizes")
        
        # --- Refs ---
        self.item_dd = ft.Dropdown(label="Search Item", expand=True, on_change=self.on_item_select, **AppStyles.get_input_style())
        self.matrix_container = ft.Column(spacing=20, scroll=ft.ScrollMode.AUTO)
        self.price_list_id = None
        self.price_type = "Wholesale"  # Default
        
        self.content = ft.Container(
            content=ft.Column([
                self.item_dd,
                ft.Divider(),
                self.matrix_container
            ], width=600, height=500, tight=True),
            padding=10
        )
        
        self.actions = [
            ft.TextButton("Cancel", on_click=lambda _: self.close_modal()),
            ft.ElevatedButton("Add to Order", icon=ft.icons.ADD_SHOPPING_CART, on_click=self.submit, style=AppStyles.primary_button_style())
        ]
        
        self.matrix_data = {} # To store the text fields: {size_val: TextField}

    def close_modal(self, e=None):
        self.open = False
        if self.page: self.page.update()

    def load_items(self, items):
        self.item_dd.options = [ft.dropdown.Option(key=str(i["id"]), text=f"{i['item_name']} ({i['item_code']})") for i in items]
        if self.page: self.update()

    def on_item_select(self, e):
        item_id = self.item_dd.value
        if not item_id or not self.price_list_id: return
        
        # 1. Fetch Item Sizes
        item_data = select("items", {"id": item_id})
        if not item_data: return
        all_sizes = item_data[0].get("sizes", [])
        
        # 2. Fetch Price List Rates for this Item
        rates_data = select("price_list_items", {"price_list_id": self.price_list_id, "item_id": item_id})
        rates_map = {r["size_value"]: r.get(f"{self.price_type.lower()}_rate", 0) for r in rates_data}
        
        # 3. Group sizes by Rate
        groups = {} # {rate: [sizes]}
        for s in sort_sizes(all_sizes):
            rate = rates_map.get(s, 0)
            if rate not in groups: groups[rate] = []
            groups[rate].append(s)
        
        # 4. Render Matrix
        self.matrix_container.controls.clear()
        self.matrix_data.clear()
        
        for rate, sizes in sorted(groups.items(), key=lambda x: _size_sort_key(sort_sizes(x[1])[0])):
            size_controls = []
            for s in sort_sizes(sizes):
                tf = ft.TextField(
                    label=s, width=70, height=40, dense=True, 
                    text_size=12, text_align=ft.TextAlign.CENTER,
                    keyboard_type=ft.KeyboardType.NUMBER
                )
                self.matrix_data[s] = {"tf": tf, "rate": rate}
                size_controls.append(tf)
            
            self.matrix_container.controls.append(
                ft.Column([
                    ft.Text(f"Rate: ₹{rate}", weight="bold", size=13, color=AppColors.PRIMARY),
                    ft.Row(size_controls, wrap=True, spacing=10)
                ], spacing=10)
            )
        
        if self.page: self.update()

    def submit(self, e):
        # Gather non-zero quantities
        results = []
        item_id = self.item_dd.value
        item_text = ""
        for opt in self.item_dd.options:
            if opt.key == item_id:
                item_text = opt.text
                break
        
        try:
            for size, data in self.matrix_data.items():
                qty = data["tf"].value
                if qty and qty.isdigit() and int(qty) > 0:
                    results.append({
                        "item_id": item_id,
                        "item_name": item_text,
                        "size": size,
                        "rate": data["rate"],
                        "qty": int(qty)
                    })
            
            if results:
                self.on_submit(results)
            self.close_modal()
        except Exception as ex:
            print(f"Matrix Submit Error: {ex}")
            self.close_modal()
