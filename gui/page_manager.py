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
from gui.pages.operations_center import OperationsCenterPage
from gui.pages.marketplace_manager import MarketplaceManagerPage


class PageManager:

    def __init__(self, container):

        self.container = container
        self.current_page = None

    # -------------------------
    # Internal Helper
    # -------------------------

    def show_page(self, page_class, *args, **kwargs):

        if self.current_page is not None:
            self.current_page.destroy()

        try:
            self.current_page = page_class(self.container, page_manager=self, *args, **kwargs)
        except TypeError:
            try:
                self.current_page = page_class(self.container, *args, **kwargs)
            except TypeError:
                self.current_page = page_class(self.container)

        self.current_page.pack(
            fill="both",
            expand=True
        )

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

    def show_operations_center(self):
        self.show_page(OperationsCenterPage)

    def show_marketplace_manager(self):
        self.show_page(MarketplaceManagerPage)

    def show_settings(self):
        self.show_page(SettingsPage)

    def show_set_manager(self):
        self.show_page(SetManagerPage)

    def show_card_manager(self, selected_set=None):
        self.show_page(CardManagerPage, selected_set=selected_set)