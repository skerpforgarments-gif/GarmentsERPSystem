import flet as ft
from core.theme import AppColors, AppStyles



class ItemMasterForm(ft.Container):
    """
    Full Item Master form based on legacy screenshot.
    Fields: Item Code, Item Order, Brand Name, Variety, Style,
    Item Name, Sizes (multi-select), Pcs/Box, Box Type, HSN Code,
    Approved, Blocked, Reason, Opening Stock (size-wise grid)
    """

    def __init__(self, on_submit=None):
        super().__init__()
        self.expand = True
        self.padding = 10
        self.on_submit = on_submit

        # =============================================
        # FIELD DEFINITIONS
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

        self.item_code = ft.TextField(label="Item Code *", width=100, **self.style_args)
        self.item_order = ft.TextField(label="Item Order", width=100, keyboard_type=ft.KeyboardType.NUMBER, value="", **self.style_args)
        
        # Brand Dropdown + Add
        self.brand_dd = ft.Dropdown(label="Brand Name", width=100, options=[], **self.style_args)
        self.brand_name = self.brand_dd # Alias for compatibility
        
        self.variety = ft.TextField(label="Variety", width=200, **self.style_args)
        
        # Style Dropdown + Add
        self.style_dd = ft.Dropdown(label="Style", width=100, options=[], **self.style_args)
        self.style = self.style_dd # Alias for compatibility
        
        self.item_name = ft.TextField(label="Item Name *", width=350, **self.style_args)
        self.hsn_code = ft.TextField(label="HSN Code", width=160, **self.style_args)
        self.inner_box_count = ft.TextField(
            label="Inner", width=80, keyboard_type=ft.KeyboardType.NUMBER, value="1", **self.style_args
        )
        self.outer_box_qty = ft.TextField(
            label="Outer", width=80, keyboard_type=ft.KeyboardType.NUMBER, value="1", **self.style_args
        )
        self.status_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="Approved", label="Approved"),
                ft.Radio(value="Blocked", label="Blocked")
            ], spacing=20),
            value="Approved"
        )
        self.reason = ft.TextField(
            label="Reason/Remarks", multiline=True, min_lines=2, max_lines=3,
            expand=True, **self.style_args
        )

        # =============================================
        # DYNAMIC METADATA CONTROLS
        # =============================================
        self.size_checkboxes = {}
        # Changed to a Row that will hold Columns (chunks of 6)
        self.size_grid_row = ft.Row(spacing=30, vertical_alignment=ft.CrossAxisAlignment.START)

        def add_custom_brand(e):
            def close_dlg(e):
                self.page.dialog.open = False
                self.page.update()

            def save_new(e):
                val = txt.value.strip()
                if val:
                    if not any(o.key == val for o in self.brand_dd.options):
                        self.brand_dd.options.append(ft.dropdown.Option(val))
                    self.brand_dd.value = val
                    close_dlg(None)
                    self.brand_dd.update()

            txt = ft.TextField(label="New Brand Name", autofocus=True)
            self.page.dialog = ft.AlertDialog(
                title=ft.Text("Add New Brand"),
                content=txt,
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg),
                    ft.TextButton("Add", on_click=save_new),
                ]
            )
            self.page.dialog.open = True
            self.page.update()

        def add_custom_style(e):
            def close_dlg(e):
                self.page.dialog.open = False
                self.page.update()

            def save_new(e):
                val = txt.value.strip()
                if val:
                    if not any(o.key == val for o in self.style_dd.options):
                        self.style_dd.options.append(ft.dropdown.Option(val))
                    self.style_dd.value = val
                    close_dlg(None)
                    self.style_dd.update()

            txt = ft.TextField(label="New Style Name", autofocus=True)
            self.page.dialog = ft.AlertDialog(
                title=ft.Text("Add New Style"),
                content=txt,
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg),
                    ft.TextButton("Add", on_click=save_new),
                ]
            )
            self.page.dialog.open = True
            self.page.update()

        def add_custom_size(e):
            def close_dlg(e):
                self.page.dialog.open = False
                self.page.update()

            def save_new(e):
                val = txt.value.strip().upper()
                if val and val not in self.size_checkboxes:
                    cb = ft.Checkbox(label=val, value=True, on_change=self.on_size_change)
                    self.size_checkboxes[val] = cb
                    # Re-render the grid into columns of 6
                    self._render_size_grid()
                    close_dlg(None)
                    self.rebuild_size_matrix()

            txt = ft.TextField(label="Size (e.g. S, 32, XL)", autofocus=True)
            self.page.dialog = ft.AlertDialog(
                title=ft.Text("Add Custom Size"),
                content=txt,
                actions=[
                    ft.TextButton("Cancel", on_click=close_dlg),
                    ft.TextButton("Add", on_click=save_new),
                ]
            )
            self.page.dialog.open = True
            self.page.update()

        self.btn_add_brand = ft.IconButton(ft.icons.ADD_CIRCLE, on_click=add_custom_brand, tooltip="Add New Brand")
        self.btn_add_style = ft.IconButton(ft.icons.ADD_CIRCLE, on_click=add_custom_style, tooltip="Add New Style")

        def select_all(e):
            for cb in self.size_checkboxes.values():
                cb.value = True
            self.rebuild_size_matrix()
            self.update()

        def unselect_all(e):
            for cb in self.size_checkboxes.values():
                cb.value = False
            self.rebuild_size_matrix()
            self.update()

        size_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("SIZE", weight="bold", size=10, color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                    ft.TextButton("All", on_click=select_all, height=30),
                    ft.TextButton("None", on_click=unselect_all, height=30),
                    ft.Container(expand=True),
                    ft.TextButton("New Size", icon=ft.icons.ADD, on_click=add_custom_size, height=30),
                ], spacing=10),
                ft.Container(
                    content=self.size_grid_row,
                    border=ft.border.all(1, "#F1F5F9"),
                    border_radius=AppStyles.BUTTON_RADIUS,
                    bgcolor="#F8FAFC",
                    padding=10,
                )
            ], spacing=4),
        )

        # =============================================
        # SIZE MATRIX GRID (stock & price per size)
        # =============================================
        self.opening_stock_inputs = {}
        self.price_inputs = {}
        self.size_matrix_grid = ft.Row(wrap=True, spacing=10)
        self.size_matrix_section = ft.Container(
            content=ft.Column([
                ft.Text("STOCK DETAILS", weight="bold", size=10, color=AppColors.PRIMARY, style=ft.TextStyle(letter_spacing=1.0)),
                self.size_matrix_grid
            ], spacing=8),
            visible=False,
            padding=15,
            border=ft.border.all(1, "#F1F5F9"),
            border_radius=AppStyles.RADIUS,
            bgcolor="#F8FAFC"
        )

        def on_size_change(e):
            self.rebuild_size_matrix()

        self.on_size_change = on_size_change # Alias for use in load_metadata

        # =============================================
        # BUTTONS
        # =============================================
        save_btn = ft.ElevatedButton(
            "Save Item", icon=ft.icons.SAVE, on_click=self._submit,
            style=AppStyles.primary_button_style(),
            height=45
        )
        clear_btn = ft.TextButton(
            "Clear", icon=ft.icons.REFRESH, on_click=self.clear,
            style=AppStyles.secondary_button_style()
        )

        # =============================================
        # LAYOUT — matches screenshot structure
        # =============================================
        self.content = ft.Column(
            controls=[
                # Row 1: Code + Order
                ft.Row([self.item_code, self.item_order], spacing=12),
                # Row 2: Brand + Variety + Style
                ft.Row([
                    ft.Row([self.brand_dd, self.btn_add_brand], spacing=0),
                    self.variety,
                    ft.Row([self.style_dd, self.btn_add_style], spacing=0)
                ], spacing=12),
                # Row 3: Item Name
                ft.Row([self.item_name], spacing=12),
                # Row 4: Inner Box Count + Outer Box Qty + HSN Code
                ft.Row([self.inner_box_count, self.outer_box_qty, self.hsn_code], spacing=12),
                # Row 5: Sizes checklist
                size_section,
                # Row 6: Status
                ft.Row([self.status_radio], spacing=20),
                # Row 7: Reason
                ft.Row([
                    ft.Container(content=self.reason, expand=True)
                ]),
                # Row 8: Size Matrix Grid (appears after sizes chosen)
                self.size_matrix_section,
                # Row 9: Actions
                ft.Row([save_btn, clear_btn], spacing=12),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

    # =========================================================
    # GET VALUES
    # =========================================================
    def get_values(self):
        selected_sizes = [size for size, cb in self.size_checkboxes.items() if cb.value]

        # Gather stock and prices from defined refs
        opening_stock = {}
        size_prices = {}
        for s in selected_sizes:
            if s in self.opening_stock_inputs:
                stk_val = self.opening_stock_inputs[s].value
                opening_stock[s] = int(float(stk_val)) if stk_val else 0
            if s in self.price_inputs:
                prc_val = self.price_inputs[s].value
                size_prices[s] = float(prc_val) if prc_val else 0

        return {
            "item_code": self.item_code.value or "",
            "item_order": int(self.item_order.value or 1),
            "brand_name": self.brand_name.value or "",
            "variety": self.variety.value or "",
            "style": self.style.value or "",
            "item_name": self.item_name.value or "",
            "sizes": selected_sizes,
            "pcs_per_inner_box": int(self.inner_box_count.value or 1),
            "boxes_per_outer_box": int(self.outer_box_qty.value or 1),
            "hsn_code": self.hsn_code.value or "",
            "is_approved": self.status_radio.value == "Approved",
            "is_blocked": self.status_radio.value == "Blocked",
            "reason": self.reason.value or "",
            "opening_stock": opening_stock,
        }

    def load_metadata(self, brands, styles, sizes):
        """Populate dropdowns and size grid from strictly discovered database metadata."""
        # 1. Brands
        self.brand_dd.options = [ft.dropdown.Option(b) for b in brands]
        
        # 2. Styles
        self.style_dd.options = [ft.dropdown.Option(s) for s in styles]
        
        # 3. Sizes (Strictly Dynamic + Intelligent Sorting)
        checked_list = [s for s, cb in self.size_checkboxes.items() if cb.value]
        self.size_checkboxes.clear()
        self.size_grid_row.controls.clear()
        
        # Intelligent Sort for Garment Sizes
        def size_sort_key(s):
            s = str(s).upper().strip()
            # Standard Size Order
            order = ["FREE", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "2XL", "3XL", "4XL", "5XL"]
            if s in order:
                return (0, order.index(s))
            # Numeric sizes
            try:
                return (1, float(s))
            except ValueError:
                # Alphanumeric fallback
                return (2, s)

        sorted_sizes = sorted(list(set(sizes)), key=size_sort_key)
        
        for s in sorted_sizes:
            cb = ft.Checkbox(label=s, value=(s in checked_list), on_change=self.on_size_change)
            self.size_checkboxes[s] = cb
        
        self._render_size_grid()
        self.rebuild_size_matrix()
        
        try:
            self.update()
        except Exception:
            pass

    def _render_size_grid(self):
        """Splits the size checkboxes into columns of 6 items each."""
        self.size_grid_row.controls.clear()
        
        # Sort keys to ensure consistent order
        def size_sort_key(s):
            s = str(s).upper().strip()
            order = ["FREE", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "2XL", "3XL", "4XL", "5XL"]
            if s in order: return (0, order.index(s))
            try: return (1, float(s))
            except ValueError: return (2, s)

        sorted_keys = sorted(self.size_checkboxes.keys(), key=size_sort_key)
        
        # Split into chunks of 6
        for i in range(0, len(sorted_keys), 6):
            chunk = sorted_keys[i : i + 6]
            col = ft.Column(
                controls=[self.size_checkboxes[s] for s in chunk if s in self.size_checkboxes],
                spacing=2
            )
            self.size_grid_row.controls.append(col)
        
        try:
            if self.size_grid_row.page:
                self.size_grid_row.update()
        except:
            pass

    def rebuild_size_matrix(self):
        """Builds a horizontal container grid for the selected sizes (Stock Count Only)."""
        selected_sizes = [s for s, cb in self.size_checkboxes.items() if cb.value]
        self.size_matrix_grid.controls.clear()
        
        # Keep old stock values if they exist
        old_stocks = {k: v.value for k, v in self.opening_stock_inputs.items()}
        self.opening_stock_inputs.clear()
        
        if not selected_sizes:
            self.size_matrix_section.visible = False
        else:
            self.size_matrix_section.visible = True
            for s in selected_sizes:
                stk_field = ft.TextField(
                    label="Stock Qty", 
                    value=old_stocks.get(s, "0"), 
                    width=100, 
                    dense=True,
                    text_align=ft.TextAlign.CENTER, 
                    keyboard_type=ft.KeyboardType.NUMBER
                )
                self.opening_stock_inputs[s] = stk_field
                
                self.size_matrix_grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(s, size=11, weight="bold", color=AppColors.TEXT_HEADER),
                            stk_field,
                        ], spacing=7, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=12,
                        bgcolor=AppColors.BG_CARD,
                        border_radius=8,
                        shadow=AppStyles.CARD_SHADOW,
                        border=ft.border.all(1, "#F0F0F0")
                    )
                )
        try:
            self.update()
        except Exception:
            pass

    # =========================================================
    # SET VALUES (Edit Mode)
    # =========================================================
    def set_values(self, data: dict):
        self.item_code.value = data.get("item_code", "")
        self.item_order.value = str(data.get("item_order", 1))
        
        # Ensure option exists before setting value
        b_val = data.get("brand_name", "")
        if b_val and not any(o.key == b_val for o in self.brand_dd.options):
            self.brand_dd.options.append(ft.dropdown.Option(b_val))
        self.brand_dd.value = b_val
        
        self.variety.value = data.get("variety", "")
        
        s_val = data.get("style", "")
        if s_val and not any(o.key == s_val for o in self.style_dd.options):
            self.style_dd.options.append(ft.dropdown.Option(s_val))
        self.style_dd.value = s_val
        
        self.item_name.value = data.get("item_name", "")
        self.inner_box_count.value = str(data.get("pcs_per_inner_box", 1))
        self.outer_box_qty.value = str(data.get("boxes_per_outer_box", 1))
        self.hsn_code.value = data.get("hsn_code", "")
        self.status_radio.value = "Blocked" if data.get("is_blocked", False) else "Approved"
        self.reason.value = data.get("reason", "")

        # Reset then apply sizes (ensure checkbox exists)
        for cb in self.size_checkboxes.values():
            cb.value = False
        for s in (data.get("sizes") or []):
            if s not in self.size_checkboxes:
                self.size_checkboxes[s] = ft.Checkbox(label=s, value=True)
                self.size_grid_row.controls.append(self.size_checkboxes[s])
            else:
                self.size_checkboxes[s].value = True

        self.rebuild_size_matrix()
        
        # Populate matrix values
        stock_data = data.get("opening_stock", {})
        price_data = data.get("size_prices", {})
        for k, v in stock_data.items():
            if k in self.opening_stock_inputs:
                self.opening_stock_inputs[k].value = str(v)
        for k, v in price_data.items():
            if k in self.price_inputs:
                self.price_inputs[k].value = str(v)

        try:
            self.update()
        except Exception:
            pass

    # =========================================================
    # CLEAR
    # =========================================================
    def clear(self, e=None):
        self.item_code.value = ""
        self.item_order.value = ""
        self.brand_name.value = ""
        self.variety.value = ""
        self.style.value = ""
        self.item_name.value = ""
        self.inner_box_count.value = "1"
        self.outer_box_qty.value = "1"
        self.hsn_code.value = ""
        self.status_radio.value = "Approved"
        self.reason.value = ""
        for cb in self.size_checkboxes.values():
            cb.value = False
        try:
            self.update()
        except Exception:
            pass

    # =========================================================
    # SUBMIT
    # =========================================================
    def _submit(self, e):
        if not self.item_code.value or not self.item_name.value:
            self.item_code.error_text = "Required" if not self.item_code.value else None
            self.item_name.error_text = "Required" if not self.item_name.value else None
            try:
                self.update()
            except Exception:
                pass
            return

        self.item_code.error_text = None
        self.item_name.error_text = None

        data = self.get_values()
        if self.on_submit:
            self.on_submit(data)
