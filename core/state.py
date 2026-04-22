class AppState:
    def __init__(self):
        # =========================
        # AUTH / USER
        # =========================
        self.current_user = None

        # =========================
        # MULTI-COMPANY (CRITICAL)
        # =========================
        self.current_company = None
        self.company_id = None

        # =========================
        # APP CONTEXT
        # =========================
        self.sales_mode = "order"  # order / packing / transport / invoice

        # =========================
        # SUBSCRIBERS
        # =========================
        self._subscribers = []

    # =========================================================
    # SUBSCRIBE
    # =========================================================
    def subscribe(self, callback):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    # =========================================================
    # UNSUBSCRIBE
    # =========================================================
    def unsubscribe(self, callback):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    # =========================================================
    # NOTIFY ALL
    # =========================================================
    def _notify(self):
        for callback in self._subscribers:
            callback(self)

    # =========================================================
    # SET USER
    # =========================================================
    def set_user(self, user):
        """
        user: dict from Supabase auth
        """
        self.current_user = user
        self._notify()

    # =========================================================
    # SET COMPANY (CRITICAL)
    # =========================================================
    def set_company(self, company: dict):
        """
        company: {
            "id": 1,
            "name": "ABC Garments"
        }
        """
        self.current_company = company
        self.company_id = company.get("id")
        self._notify()

    # =========================================================
    # SET SALES MODE
    # =========================================================
    def set_sales_mode(self, mode: str):
        self.sales_mode = mode
        self._notify()

    # =========================================================
    # CLEAR SESSION (LOGOUT)
    # =========================================================
    def clear(self):
        self.current_user = None
        self.current_company = None
        self.company_id = None
        self.sales_mode = "order"
        self._notify()


# =========================================================
# SINGLETON INSTANCE
# =========================================================
state = AppState()
