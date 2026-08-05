import traceback

from gui.pages.dashboard import DashboardPage
from gui.pages.build import BuildPage
from gui.pages.inventory import InventoryPage
from gui.pages.images import ImagesPage
from gui.pages.pricing import PricingPage
from gui.pages.statistics import StatisticsPage
from gui.pages.sales import SalesPage
from gui.pages.settings import SettingsPage
from gui.pages.set_manager import SetManagerPage
from gui.pages.card_manager import CardManagerPage
from gui.pages.business_analytics import BusinessAnalyticsPage
from gui.pages.marketplace_manager import MarketplaceManagerPage


class PageManager:

    def __init__(self, container):

        self.container = container
        self.current_page = None
        self._page_instances = {}

    # -------------------------
    # Internal Helper
    # -------------------------

    def show_page(self, page_class, *args, **kwargs):

        page_key = self._page_key(page_class)
        created = False
        previous_page = self.current_page
        deferred_card_manager_set = None

        page = self._page_instances.get(page_key)
        if page is None:
            try:
                page = self._create_page(page_class, *args, **kwargs)
            except Exception:
                print(f"[PageManager] Failed to create page: {page_key}")
                traceback.print_exc()
                return
            self._page_instances[page_key] = page
            created = True
        elif page_class is CardManagerPage:
            selected_set = kwargs.get("selected_set")
            if selected_set:
                deferred_card_manager_set = selected_set

        if previous_page is not None and previous_page is not page:
            previous_page.pack_forget()

        self.current_page = page
        self.current_page.pack(
            fill="both",
            expand=True
        )

        if deferred_card_manager_set:
            page.load_set(deferred_card_manager_set)

        if not created and page_class is not CardManagerPage:
            refresh_method = getattr(page, "refresh", None)
            if callable(refresh_method):
                try:
                    refresh_method()
                except Exception:
                    print(f"[PageManager] Refresh failed for page: {page_key}")
                    traceback.print_exc()

    def _create_page(self, page_class, *args, **kwargs):
        try:
            return page_class(self.container, page_manager=self, *args, **kwargs)
        except TypeError as exc:
            message = str(exc)
            constructor_signature_issue = (
                "unexpected keyword argument" in message
                or "positional argument" in message
                or "required positional argument" in message
            )
            if not constructor_signature_issue:
                raise
            try:
                return page_class(self.container, *args, **kwargs)
            except TypeError as retry_exc:
                retry_message = str(retry_exc)
                retry_signature_issue = (
                    "unexpected keyword argument" in retry_message
                    or "positional argument" in retry_message
                    or "required positional argument" in retry_message
                )
                if not retry_signature_issue:
                    raise
                return page_class(self.container)

    def _page_key(self, page_class):
        return page_class.__name__

    def notify_sets_updated(self):
        page = self.current_page
        if page is None:
            return

        refresh_method = getattr(page, "refresh", None)
        if callable(refresh_method):
            try:
                refresh_method()
            except Exception:
                page_name = page.__class__.__name__
                print(f"[PageManager] notify_sets_updated refresh failed for page: {page_name}")
                traceback.print_exc()

    # -------------------------
    # Public Methods
    # -------------------------

    def show_dashboard(self):
        self.show_page(DashboardPage)

    def show_build(self):
        self.show_page(BuildPage)

    def show_inventory(self):
        self.show_page(InventoryPage)

    def show_images(self):
        self.show_page(ImagesPage)

    def show_pricing(self):
        self.show_page(PricingPage)

    def show_statistics(self):
        self.show_page(StatisticsPage)

    def show_sales(self):
        self.show_page(SalesPage)

    def show_business_analytics(self):
        self.show_page(BusinessAnalyticsPage)

    def show_marketplace_manager(self):
        self.show_page(MarketplaceManagerPage)

    def show_settings(self):
        self.show_page(SettingsPage)

    def show_set_manager(self):
        self.show_page(SetManagerPage)

    def show_card_manager(self, selected_set=None):
        self.show_page(CardManagerPage, selected_set=selected_set)