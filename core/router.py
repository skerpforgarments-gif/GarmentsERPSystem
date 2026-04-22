from screens.dashboard import DashboardScreen
from screens.masters import MastersScreen
from screens.sales import SalesScreen
from screens.finance import FinanceScreen
from screens.reports import ReportsScreen
from screens.settings import SettingsScreen
from screens.login import LoginScreen


class Router:
    def __init__(self, layout):
        """
        layout: MainLayout instance
        """
        self.layout = layout

        # =========================
        # ROUTE REGISTRY
        # =========================
        self.routes = {
            "login": LoginScreen,
            "dashboard": DashboardScreen,
            "masters": MastersScreen,
            "sales": SalesScreen,
            "finance": FinanceScreen,
            "reports": ReportsScreen,
            "settings": SettingsScreen,
        }

    # =========================================================
    # NAVIGATE
    # =========================================================
    def go(self, route_name: str, **kwargs):
        if route_name not in self.routes:
            print(f"[Router] Invalid route: {route_name}")
            return

        screen_class = self.routes[route_name]

        try:
            # Create screen instance
            if route_name == "login":
                screen = screen_class(on_login_success=lambda: self.go("dashboard"))
            else:
                screen = screen_class(**kwargs) if kwargs else screen_class()

            # Render through layout
            self.layout.set_screen(screen)

        except Exception as e:
            print(f"[Router] Error loading {route_name}: {e}")

    # =========================================================
    # OPTIONAL: RELOAD CURRENT SCREEN
    # =========================================================
    def reload(self, route_name: str, **kwargs):
        self.go(route_name, **kwargs)
