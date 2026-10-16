"""
RÉSIVO — Maintenance Photo Viewer Dialog & Async Fetch Worker
High-contrast obsidian dialog with pan/zoom controls (fit / − / +, 25%–400%)
and async background loading to keep the UI thread fully responsive.
"""
from __future__ import annotations

import urllib.request
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from .icons import get_icon, get_pixmap
    from .theme import apply_button_style
except (ImportError, ValueError):
    try:
        from ..icons import get_icon, get_pixmap
        from ..theme import apply_button_style
    except (ImportError, ValueError):
        from desktop.app.ui.icons import get_icon, get_pixmap
        from desktop.app.ui.theme import apply_button_style


class ClickablePhotoLabel(QLabel):
    """QLabel that emits a clicked signal on left mouse button press."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PhotoFetchWorker(QThread):
    """Fetches image bytes in a background thread to prevent UI freezing."""
    loaded = Signal(bytes)
    failed = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        if not self.url or not isinstance(self.url, str) or not self.url.startswith(("http://", "https://")):
            if not self._stopped:
                self.failed.emit("Invalid image URL")
            return

        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (RÉSIVO Staff Console)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                chunks = []
                while not self._stopped:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                if not self._stopped:
                    self.loaded.emit(b"".join(chunks))
        except Exception as exc:  # noqa: BLE001
            if not self._stopped:
                self.failed.emit(str(exc))


PHOTO_VIEWER_QSS = """
QDialog#photoViewerDialog {
    background-color: #0a0c13;
    color: #f8fafc;
}

QFrame#viewerCard {
    background-color: #10131d;
    border: 1px solid #1c2234;
    border-radius: 12px;
}

QScrollArea#scrollArea {
    background-color: #07090e;
    border: 1px solid #1a2030;
    border-radius: 8px;
}

QLabel {
    background: transparent;
    border: none;
    color: #f8fafc;
}

QScrollBar:vertical {
    border: none;
    background: #090a0f;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #252c40;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #3b4666;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #090a0f;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #252c40;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #3b4666;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""


class PhotoViewerDialog(QDialog):
    """Full-size maintenance photo viewer with zoom and async full-res swap."""

    MIN_SCALE = 0.25
    MAX_SCALE = 4.0
    ZOOM_STEP = 0.25

    def __init__(
        self,
        parent=None,
        initial_pixmap: QPixmap | None = None,
        image_url: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("photoViewerDialog")
        self.setWindowTitle("Maintenance Fault Photo — RÉSIVO")
        self.setMinimumSize(640, 480)
        self.resize(880, 640)
        self.setStyleSheet(PHOTO_VIEWER_QSS)

        self.full_pixmap: QPixmap | None = initial_pixmap
        self.image_url: str | None = image_url
        self.scale_factor: float = 1.0
        self.is_fit_mode: bool = True
        self.worker: PhotoFetchWorker | None = None

        # Outer Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Card Container
        card = QFrame()
        card.setObjectName("viewerCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Top Bar: Title & Controls
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        title_icon = QLabel()
        title_icon.setPixmap(get_pixmap("maintenance", size=18, color="#38bdf8"))
        top_bar.addWidget(title_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Ticket Fault Evidence")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #f8fafc;")
        self.status_label = QLabel("Loading photo…")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("font-size: 11px; color: #64748b;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(self.status_label)
        top_bar.addLayout(title_vbox)

        top_bar.addStretch(1)

        # Zoom Controls
        zoom_bar = QHBoxLayout()
        zoom_bar.setSpacing(6)

        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setObjectName("zoomFitBtn")
        self.btn_fit.setCheckable(True)
        self.btn_fit.setChecked(True)
        apply_button_style(self.btn_fit, "secondary")
        self.btn_fit.clicked.connect(self.set_fit_mode)
        zoom_bar.addWidget(self.btn_fit)

        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setObjectName("zoomOutBtn")
        self.btn_zoom_out.setToolTip("Zoom Out (min 25%)")
        self.btn_zoom_out.setFixedWidth(36)
        apply_button_style(self.btn_zoom_out, "secondary")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_bar.addWidget(self.btn_zoom_out)

        self.zoom_label = QLabel("Fit (100%)")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 700; min-width: 75px;")
        zoom_bar.addWidget(self.zoom_label)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setObjectName("zoomInBtn")
        self.btn_zoom_in.setToolTip("Zoom In (max 400%)")
        self.btn_zoom_in.setFixedWidth(36)
        apply_button_style(self.btn_zoom_in, "secondary")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_bar.addWidget(self.btn_zoom_in)

        zoom_bar.addSpacing(10)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("closeBtn")
        apply_button_style(self.btn_close, "secondary")
        self.btn_close.clicked.connect(self.accept)
        zoom_bar.addWidget(self.btn_close)

        top_bar.addLayout(zoom_bar)
        card_layout.addLayout(top_bar)

        # Scroll Area for Image View
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("scrollArea")
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidgetResizable(False)

        # Container inside ScrollArea
        self.image_container = QWidget()
        self.image_container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background: transparent;")
        container_layout.addWidget(self.image_label)

        self.scroll_area.setWidget(self.image_container)
        card_layout.addWidget(self.scroll_area, 1)

        root_layout.addWidget(card)

        # Initial Render
        if self.full_pixmap and not self.full_pixmap.isNull():
            self.status_label.setText(f"{self.full_pixmap.width()} × {self.full_pixmap.height()} px (preview)")
            self._apply_fit()
        else:
            self.image_label.setText("No photo preview available")
            self.status_label.setText("No preview image")

        # Async fetch full-res if URL is provided
        if self.image_url:
            self.status_label.setText("Fetching full-resolution photo…")
            self.worker = PhotoFetchWorker(self.image_url, parent=None)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.loaded.connect(self._on_full_loaded)
            self.worker.failed.connect(self._on_full_failed)
            self.worker.start()

    def set_fit_mode(self):
        self.is_fit_mode = True
        self.btn_fit.setChecked(True)
        self._apply_fit()

    def zoom_in(self):
        self.is_fit_mode = False
        self.btn_fit.setChecked(False)
        target = min(self.MAX_SCALE, round(self.scale_factor + self.ZOOM_STEP, 2))
        self.set_scale(target)

    def zoom_out(self):
        self.is_fit_mode = False
        self.btn_fit.setChecked(False)
        target = max(self.MIN_SCALE, round(self.scale_factor - self.ZOOM_STEP, 2))
        self.set_scale(target)

    def set_scale(self, scale: float):
        self.scale_factor = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        self._render_pixmap()
        pct = int(round(self.scale_factor * 100))
        self.zoom_label.setText(f"{pct}%")

    def _apply_fit(self):
        if not self.full_pixmap or self.full_pixmap.isNull():
            self.zoom_label.setText("—")
            return

        vw = max(50, self.scroll_area.viewport().width() - 20)
        vh = max(50, self.scroll_area.viewport().height() - 20)
        pw = max(1, self.full_pixmap.width())
        ph = max(1, self.full_pixmap.height())

        fit_scale = min(vw / pw, vh / ph)
        fit_scale = max(self.MIN_SCALE, min(self.MAX_SCALE, fit_scale))
        self.scale_factor = fit_scale
        self._render_pixmap()

        pct = int(round(self.scale_factor * 100))
        self.zoom_label.setText(f"Fit ({pct}%)")

    def _render_pixmap(self):
        if not self.full_pixmap or self.full_pixmap.isNull():
            self.image_label.setText("No photo preview available")
            self.image_container.resize(200, 100)
            return

        target_w = max(1, int(round(self.full_pixmap.width() * self.scale_factor)))
        target_h = max(1, int(round(self.full_pixmap.height() * self.scale_factor)))

        scaled = self.full_pixmap.scaled(
            target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.image_container.resize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_fit_mode:
            self._apply_fit()

    def _on_full_loaded(self, data: bytes):
        pix = QPixmap()
        if pix.loadFromData(data) and not pix.isNull():
            self.full_pixmap = pix
            self.status_label.setText(f"{pix.width()} × {pix.height()} px (full resolution)")
            if self.is_fit_mode:
                self._apply_fit()
            else:
                self._render_pixmap()
        else:
            if not self.full_pixmap:
                self.status_label.setText("Image format unsupported")
            else:
                self.status_label.setText("Showing preview (full-res format unsupported)")

    def _on_full_failed(self, err_msg: str):
        if self.full_pixmap and not self.full_pixmap.isNull():
            self.status_label.setText("Showing preview (full-res download unavailable)")
        else:
            self.status_label.setText("Failed to load photo")

    def _cleanup_worker(self):
        if self.worker is not None:
            try:
                self.worker.loaded.disconnect()
                self.worker.failed.disconnect()
            except RuntimeError:
                pass
            self.worker.stop()
            self.worker = None

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_worker()
        super().reject()

    def accept(self):
        self._cleanup_worker()
        super().accept()
