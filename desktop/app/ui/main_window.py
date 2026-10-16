from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QStatusBar, QLabel,
)
from ..client import current_role
from .live_sync import LiveSyncWorker
from .icons import get_icon, get_pixmap
from .theme import DESKTOP_STYLESHEET
from .pages.overview import OverviewPage
from .pages.pending import PendingPage
from .pages.residents import ResidentsPage
from .pages.rooms import RoomsPage
from .pages.maintenance import MaintenancePage
from .pages.room_changes import RoomChangesPage
from .pages.official_list import OfficialListPage
from .pages.staff_accounts import StaffAccountsPage
from .pages.settings import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = current_role(client)
        self.setWindowTitle("Residence Staff Console — Tlemcen [LIVE MODE]")
        self.resize(1180, 760)
        self.setStyleSheet(DESKTOP_STYLESHEET)

        # Main Layout Container
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Institutional Control Header
        header_bar = QWidget()
        header_bar.setStyleSheet("""
            QWidget {
                background-color: #090a0f;
                border-bottom: 1px solid #161925;
            }
        """)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(14)

        # Brand / Institutional Crest
        crest_label = QLabel()
        crest_label.setPixmap(get_pixmap("crest", size=24, color="#38bdf8"))
        header_layout.addWidget(crest_label)

        title_container = QVBoxLayout()
        title_container.setSpacing(1)
        title_lbl = QLabel("Cité Universitaire — Residence Tlemcen")
        title_lbl.setStyleSheet("color: #f8fafc; font-weight: 800; font-size: 14px; letter-spacing: 0.3px;")
        sub_lbl = QLabel("Dormitory Operations & Facility Management Console")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_container.addWidget(title_lbl)
        title_container.addWidget(sub_lbl)
        header_layout.addLayout(title_container)

        header_layout.addStretch(1)

        # Operator Role Badge
        role_text = "ADMINISTRATOR" if self.role == "admin" else "HOUSING STAFF"
        role_badge = QLabel(f"● {role_text}")
        if self.role == "admin":
            role_badge.setStyleSheet("""
                color: #38bdf8;
                background-color: #082f49;
                border: 1px solid #0284c7;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            role_badge.setStyleSheet("""
                color: #94a3b8;
                background-color: #141724;
                border: 1px solid #283145;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            """)
        header_layout.addWidget(role_badge)

        root_layout.addWidget(header_bar)

        # 2. Main Body: Sidebar + Stacked Pages
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left Sidebar Navigation
        self.nav = QListWidget()
        self.nav.setObjectName("sidebarNav")
        self.nav.setFixedWidth(230)
        self.nav.setIconSize(QSize(18, 18))
        body_layout.addWidget(self.nav)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #0c0e15;")
        body_layout.addWidget(self.stack, 1)

        root_layout.addWidget(body_widget, 1)

        # Pages instantiation
        self.pages: dict[str, QWidget] = {}
        self.overview_page = OverviewPage(client)
        self.pending_page = PendingPage(client)
        self.residents_page = ResidentsPage(client)
        self.rooms_page = RoomsPage(client)
        self.maintenance_page = MaintenancePage(client)
        self.room_changes_page = RoomChangesPage(client)
        self.official_list_page = OfficialListPage(client)

        self._add_nav_item("Overview", "overview", self.overview_page)
        self._add_nav_item("Pending accounts", "pending", self.pending_page)
        self._add_nav_item("Residents", "residents", self.residents_page)
        self._add_nav_item("Rooms", "rooms", self.rooms_page)
        self._add_nav_item("Maintenance", "maintenance", self.maintenance_page)
        self._add_nav_item("Room changes", "room_changes", self.room_changes_page)
        self._add_nav_item("Official list", "official_list", self.official_list_page)

        if self.role == "admin":
            self.staff_accounts_page = StaffAccountsPage(client)
            self._add_nav_item("Staff accounts", "staff_accounts", self.staff_accounts_page)

        self.settings_page = SettingsPage(client)
        self._add_nav_item("Settings", "settings", self.settings_page)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # 3. Status Bar with Live Sync & Alerts
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Connecting to Supabase Live Sync...")

        # Start live background sync worker
        self.sync_worker = LiveSyncWorker(client, interval_ms=2000)
        self.sync_worker.sync_tick.connect(self.on_live_sync_tick)
        self.sync_worker.alert_event.connect(self.on_live_alert)
        self.sync_worker.start()

    def _add_nav_item(self, title: str, icon_name: str, widget: QWidget):
        self.pages[title] = widget
        item = QListWidgetItem(title)
        item.setIcon(get_icon(icon_name, size=18, color="#cbd5e1"))
        self.nav.addItem(item)
        self.stack.addWidget(widget)

    def on_live_alert(self, msg: str):
        self.status_bar.showMessage(f"🔔 LIVE EVENT: {msg}", 10000)

    def on_live_sync_tick(self, data: dict):
        pending_students = data.get("pending_students", [])
        reports = data.get("reports", [])
        open_reports_count = data.get("open_reports_count", 0)
        pending_requests = data.get("pending_requests", [])
        timestamp = data.get("timestamp", "")

        # 1. Update status bar message if no urgent event is displayed
        current_msg = self.status_bar.currentMessage()
        if not current_msg or not current_msg.startswith("🔔 LIVE EVENT:"):
            self.status_bar.showMessage(f"Live sync active • Last update: {timestamp}")

        # 2. Update badge counts on sidebar navigation items
        p_count = len(pending_students)
        m_count = open_reports_count
        r_count = len(pending_requests)

        for i in range(self.nav.count()):
            item = self.nav.item(i)
            text = item.text().split(" (")[0]
            if text == "Pending accounts":
                item.setText(f"Pending accounts ({p_count})" if p_count > 0 else "Pending accounts")
            elif text == "Maintenance":
                item.setText(f"Maintenance ({m_count})" if m_count > 0 else "Maintenance")
            elif text == "Room changes":
                item.setText(f"Room changes ({r_count})" if r_count > 0 else "Room changes")

        # 3. Deliver live data to pages
        self.overview_page.apply_live_data(p_count, m_count, r_count)
        self.pending_page.apply_live_data(pending_students)
        self.maintenance_page.apply_live_data(reports)
        self.room_changes_page.apply_live_data(pending_requests)

    def closeEvent(self, event):
        if hasattr(self, "sync_worker") and self.sync_worker.isRunning():
            self.sync_worker.stop()
            if not self.sync_worker.wait(3000):
                self.sync_worker.terminate()
                self.sync_worker.wait(1000)
        if hasattr(self, "settings_page") and self.settings_page.health_worker.isRunning():
            self.settings_page.health_worker.stop()
            if not self.settings_page.health_worker.wait(3000):
                self.settings_page.health_worker.terminate()
                self.settings_page.health_worker.wait(1000)
        super().closeEvent(event)
