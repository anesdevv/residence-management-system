from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget,
)
from ..client import current_role
from .pages.overview import OverviewPage
from .pages.pending import PendingPage
from .pages.residents import ResidentsPage
from .pages.rooms import RoomsPage
from .pages.maintenance import MaintenancePage
from .pages.room_changes import RoomChangesPage


class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = current_role(client)
        self.setWindowTitle("Residence Staff Console — Tlemcen")
        self.resize(1000, 680)

        self.nav = QListWidget()
        self.nav.setFixedWidth(200)
        self.stack = QStackedWidget()

        self.pages: dict[str, QWidget] = {}
        self._add_page("Overview", OverviewPage(client))
        self._add_page("Pending accounts", PendingPage(client))
        self._add_page("Residents", ResidentsPage(client))
        self._add_page("Rooms", RoomsPage(client))
        self._add_page("Maintenance", MaintenancePage(client))
        self._add_page("Room changes", RoomChangesPage(client))

        # Later tasks append more pages via self._add_page(...).

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self.nav.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget):
        self.pages[title] = widget
        self.nav.addItem(title)
        self.stack.addWidget(widget)
