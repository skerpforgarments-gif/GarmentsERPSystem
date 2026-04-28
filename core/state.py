import json
import os

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
        # APP CONTEXT & SETTINGS
        # =========================
        self.sales_mode = "order"  # order / packing / transport / invoice
        self.settings = {"direct_invoice": False}
        self.load_settings()

        # =========================
        # SUBSCRIBERS
        # =========================
        self._subscribers = []

    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    self.settings.update(json.load(f))
        except:
            pass
            
    def save_settings(self):
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
            self._notify()
        except:
            pass

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
