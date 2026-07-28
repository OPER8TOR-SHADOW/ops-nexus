import customtkinter as ctk
from datetime import datetime

from gui.theme import *
from gui.services.operations_center_service import OperationsCenterService


SEVERITY_COLORS = {
    "low": SUBTEXT,
    "medium": WARNING,
    "high": ERROR,
}


class OperationsCenterPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):
        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.service = OperationsCenterService()

        self.section_frames = {}
        self.score_labels = {}
        self.score_bars = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self.refresh()

    # -------------------------
    # Layout
    # -------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="Operations Center",
            font=(FONT, 30, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            header,
            text="",
            font=(FONT, 12),
            text_color=MUTED,
        )
        self.status_label.pack(side="right")

    def _build_body(self):
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.body.grid_columnconfigure(0, weight=1)

        self._build_score_section(self.body)
        self._build_recommendation_section(self.body, "Inventory Health", "inventory_health")
        self._build_recommendation_section(self.body, "Sales Insights", "sales_insights")
        self._build_recommendation_section(self.body, "Pricing Suggestions", "pricing_suggestions")
        self._build_recommendation_section(self.body, "Listing Opportunities", "listing_opportunities")
        self._build_recommendation_section(self.body, "Business Alerts", "business_alerts")

    def _build_score_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        top = ctk.CTkFrame(section, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 8))

        ctk.CTkLabel(top, text="Daily Operations Score", font=(FONT, 18, "bold"), text_color=TEXT).pack(side="left")

        self.overall_label = ctk.CTkLabel(top, text="0 / 100", font=(FONT, 20, "bold"), text_color=TEXT)
        self.overall_label.pack(side="right")

        score_names = [
            ("inventory_health", "Inventory Health"),
            ("listing_readiness", "Listing Readiness"),
            ("pricing_quality", "Pricing Quality"),
            ("image_coverage", "Image Coverage"),
            ("sales_activity", "Sales Activity"),
            ("overall_business_health", "Overall Business Health"),
        ]

        for key, label in score_names:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)

            ctk.CTkLabel(row, text=label, font=(FONT, 12, "bold"), text_color=SUBTEXT, width=190, anchor="w").pack(side="left")

            bar = ctk.CTkProgressBar(row)
            bar.pack(side="left", fill="x", expand=True, padx=(8, 8))
            bar.set(0)

            value_label = ctk.CTkLabel(row, text="0", font=(FONT, 12, "bold"), text_color=TEXT, width=40)
            value_label.pack(side="right")

            self.score_bars[key] = bar
            self.score_labels[key] = value_label

    def _build_recommendation_section(self, parent, title, key):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 8))

        ctk.CTkLabel(header, text=title, font=(FONT, 18, "bold"), text_color=TEXT).pack(side="left")

        count = ctk.CTkLabel(header, text="0 recommendation(s)", font=(FONT, 11), text_color=MUTED)
        count.pack(side="right")

        frame = ctk.CTkFrame(section, fg_color="transparent")
        frame.pack(fill="x", padx=14, pady=(0, 12))

        self.section_frames[key] = {
            "container": frame,
            "count": count,
        }

    # -------------------------
    # Refresh
    # -------------------------

    def refresh(self):
        snapshot = self.service.get_operations_snapshot()

        self._render_score(snapshot.get("daily_score", {}))
        self._render_section("inventory_health", snapshot.get("inventory_health", []))
        self._render_section("sales_insights", snapshot.get("sales_insights", []))
        self._render_section("pricing_suggestions", snapshot.get("pricing_suggestions", []))
        self._render_section("listing_opportunities", snapshot.get("listing_opportunities", []))
        self._render_section("business_alerts", snapshot.get("business_alerts", []))

        self.status_label.configure(text=f"Updated {datetime_now_text()}")

    def _render_score(self, score):
        overall = int(score.get("overall_business_health", 0) or 0)
        self.overall_label.configure(text=f"{overall} / 100")

        for key, label in self.score_labels.items():
            value = int(score.get(key, 0) or 0)
            label.configure(text=str(value))

            bar = self.score_bars[key]
            bar.set(max(0.0, min(1.0, value / 100.0)))

    def _render_section(self, key, recommendations):
        section = self.section_frames[key]
        container = section["container"]

        for child in container.winfo_children():
            child.destroy()

        section["count"].configure(text=f"{len(recommendations)} recommendation(s)")

        if not recommendations:
            ctk.CTkLabel(
                container,
                text="No issues detected for this section.",
                font=(FONT, 12),
                text_color=SUCCESS,
            ).pack(anchor="w")
            return

        for rec in recommendations:
            row = ctk.CTkFrame(container, fg_color=SUBTEXT, corner_radius=10)
            row.pack(fill="x", pady=4)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            severity = str(rec.get("severity") or "low")
            color = SEVERITY_COLORS.get(severity, SUBTEXT)

            ctk.CTkLabel(
                left,
                text=f"[{severity.upper()}] {rec.get('title', 'Recommendation')}",
                font=(FONT, 12, "bold"),
                text_color=color,
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                left,
                text=str(rec.get("detail") or ""),
                font=(FONT, 11),
                text_color=TEXT,
                anchor="w",
                justify="left",
                wraplength=760,
            ).pack(anchor="w", pady=(2, 0))

            action_label = str(rec.get("action_label") or "Open")
            payload = rec.get("action") or {}

            ctk.CTkButton(
                row,
                text=action_label,
                width=120,
                command=lambda p=payload: self._run_action(p),
            ).pack(side="right", padx=10, pady=10)

    # -------------------------
    # Actions
    # -------------------------

    def _run_action(self, payload):
        action = str(payload.get("action") or "")

        if action == "open_card":
            set_id = payload.get("set_id")
            if self.page_manager is not None and hasattr(self.page_manager, "show_card_manager"):
                self.page_manager.show_card_manager(selected_set=set_id)
            return

        if action == "open_inventory":
            if self.page_manager is not None and hasattr(self.page_manager, "show_inventory"):
                self.page_manager.show_inventory()
            return

        if action == "open_pricing":
            if self.page_manager is not None and hasattr(self.page_manager, "show_pricing"):
                self.page_manager.show_pricing()
            return

        if action == "open_images":
            if self.page_manager is not None and hasattr(self.page_manager, "show_images"):
                self.page_manager.show_images()
            return

        if action == "record_sale":
            if self.page_manager is not None and hasattr(self.page_manager, "show_sales"):
                self.page_manager.show_sales()
            return

        if action == "queue_ebay":
            finish_id = payload.get("finish_id")
            set_id = payload.get("set_id")
            if finish_id:
                self.service.db_service.queue_finish_for_ebay(finish_id, listing_group=set_id)
                self.service._cache = {}
                self.refresh()
            return

        if action == "generate_csv":
            set_id = payload.get("set_id")
            self.service.db_service.export_queue_to_csv(set_id=set_id)
            self.service._cache = {}
            self.refresh()
            return

    # -------------------------
    # Lifecycle
    # -------------------------

    def destroy(self):
        service = getattr(self, "service", None)
        if service is not None:
            service.close()
        super().destroy()


def datetime_now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
