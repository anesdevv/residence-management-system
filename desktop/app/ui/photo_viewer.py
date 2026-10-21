"""RÉSIVO — maintenance photo viewer dialog and async fetch worker (visual only).

docs/DESIGN.md §4/§6: ``PhotoViewerDialog`` is a modal **navy-900 scrim** at
~92 % opacity over a transparent stage that centres the photo, with a floating
light toolbar (fit · zoom out · percentage · zoom in · close) built from
token-styled ``IconButton``s/``Button`` whose tooltips name the keyboard
shortcut (``F`` fit, ``+``/``−`` zoom, ``Esc`` close, arrow keys pan when
zoomed) and an ``e2`` drop shadow.

Behaviour is frozen
-------------------
``ClickablePhotoLabel`` still emits ``clicked`` on a left press only.
``PhotoFetchWorker(url, parent=None)`` still downloads one URL on a background
thread with a 15 s timeout and the ``loaded`` / ``failed`` / ``stop()`` /
``_stopped`` surface. The dialog keeps ``full_pixmap``, ``image_url``,
``scale_factor``, ``is_fit_mode``, ``worker``, ``MIN_SCALE`` (0.25),
``MAX_SCALE`` (4.0), ``ZOOM_STEP``, ``zoom_in`` / ``zoom_out`` /
``set_fit_mode`` / ``set_scale`` / ``_apply_fit`` / ``_render_pixmap`` /
``resizeEvent`` / ``_on_full_loaded`` / ``_on_full_failed`` /
``_cleanup_worker`` / ``closeEvent`` / ``reject`` / ``accept``, the checkable
``btn_fit``, the ``zoom_label`` contract (``Fit`` in fit mode, ``25 %`` /
``400 %`` exactly at the limits) and the ``status_label`` size line
(``200 × 150``).
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from . import theme
    from .components import Button, IconButton
    from .icons import get_pixmap
    from .theme import C, S, apply_elevation, qcolor
except (ImportError, ValueError):  # pragma: no cover - direct module execution
    from desktop.app.ui import theme
    from desktop.app.ui.components import Button, IconButton
    from desktop.app.ui.icons import get_pixmap
    from desktop.app.ui.theme import C, S, apply_elevation, qcolor


class ClickablePhotoLabel(QLabel):
    """QLabel that emits a clicked signal on left mouse button press."""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# Live fetchers are kept here until their QThread emits finished.
_ACTIVE_FETCHERS: set[PhotoFetchWorker] = set()


def running_photo_fetchers() -> list[PhotoFetchWorker]:
    """Fetchers whose QThread has not finished yet."""
    return [worker for worker in list(_ACTIVE_FETCHERS) if worker.isRunning()]


def stop_photo_fetchers() -> None:
    """Ask every live fetcher to stop; used by the main-window shutdown."""
    for worker in list(_ACTIVE_FETCHERS):
        worker.stop()


class PhotoFetchWorker(QThread):
    """Fetches image bytes in a background thread to prevent UI freezing."""

    loaded = Signal(bytes)
    failed = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._stopped = False
        # Keep the wrapper alive until the thread really finishes.  Callers
        # disconnect signals and drop their own reference when a preview is
        # replaced or a dialog closes; without this registry Python could
        # destroy a running QThread ("Destroyed while thread is still running").
        _ACTIVE_FETCHERS.add(self)
        self.finished.connect(self._untrack)

    def _untrack(self):
        _ACTIVE_FETCHERS.discard(self)

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


# Alpha of the modal scrim over the console behind the viewer (navy-900 ~92 %).
_SCRIM_ALPHA = 235


def _rgba(token: str, alpha: int) -> str:
    """``rgba(r, g, b, a)`` string for a colour token at a 0–255 alpha."""
    color = qcolor(token)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def _viewer_qss() -> str:
    """Viewer QSS — every value interpolated from theme tokens (no raw hex)."""
    return f"""
QDialog#photoViewerDialog {{
    background-color: {_rgba("navy-900", _SCRIM_ALPHA)};
}}
QFrame#viewerToolbar {{
    background-color: {C("surface")};
    border: 1px solid {C("border")};
    border-radius: {C("radius-card")};
}}
QLabel#viewerTitle {{ color: {C("text-on-dark")}; }}
QLabel#viewerStatus {{ color: {C("text-on-dark-muted")}; }}
QLabel#imageLabel {{ color: {C("text-on-dark-muted")}; }}
QLabel#zoomLabel {{
    color: {C("text-primary")};
    font-size: {C("fs-small")};
    font-weight: {C("fw-semibold")};
}}
QLabel#panHint {{ color: {C("text-muted")}; font-size: {C("fs-small")}; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; }}
QScrollBar::handle:vertical {{
    background-color: {_rgba("text-on-dark", 90)};
    border-radius: {C("radius-bar")};
    min-height: {S("space-6")}px;
}}
QScrollBar::handle:horizontal {{
    background-color: {_rgba("text-on-dark", 90)};
    border-radius: {C("radius-bar")};
    min-width: {S("space-6")}px;
}}
""".strip()


# Kept public: the dialog style sheet was a module-level constant before.
PHOTO_VIEWER_QSS = _viewer_qss()


class PhotoViewerDialog(QDialog):
    """Full-size maintenance photo viewer with zoom and async full-res swap."""

    MIN_SCALE = 0.25
    MAX_SCALE = 4.0
    ZOOM_STEP = 0.25
    # Arrow-key pan step (tokens only).
    PAN_STEP = S("space-8")

    def __init__(
        self,
        parent=None,
        initial_pixmap: QPixmap | None = None,
        image_url: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("photoViewerDialog")
        self.setWindowTitle("Maintenance fault photo — RÉSIVO")
        self.setMinimumSize(640, 480)
        self.resize(880, 640)
        # Translucent top level so the 92 % navy scrim really dims the console.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(PHOTO_VIEWER_QSS)

        self.full_pixmap: QPixmap | None = initial_pixmap
        self.image_url: str | None = image_url
        self.scale_factor: float = 1.0
        self.is_fit_mode: bool = True
        self.worker: PhotoFetchWorker | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-4"))
        root_layout.setSpacing(S("space-3"))

        # ------------------------------------------------------------- header
        header = QHBoxLayout()
        header.setSpacing(S("space-2"))
        title_icon = QLabel()
        title_icon.setPixmap(get_pixmap("image", S("size-icon"), C("text-on-dark")))
        header.addWidget(title_icon, 0, Qt.AlignmentFlag.AlignTop)

        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        title_lbl = QLabel("Ticket fault evidence")
        theme.apply_role(title_lbl, "h3")
        title_lbl.setObjectName("viewerTitle")
        self.status_label = QLabel("Loading photo…")
        self.status_label.setObjectName("viewerStatus")
        theme.apply_role(self.status_label, "small")
        theme.enable_tabular(self.status_label)
        title_column.addWidget(title_lbl)
        title_column.addWidget(self.status_label)
        header.addLayout(title_column, 1)
        root_layout.addLayout(header)

        # ------------------------------------------------- transparent stage
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("photoStage")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(False)

        self.image_container = QWidget()
        self.image_container.setObjectName("imageContainer")
        self.image_container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: transparent;")
        container_layout.addWidget(self.image_label)

        self.scroll_area.setWidget(self.image_container)
        root_layout.addWidget(self.scroll_area, 1)

        # ------------------------------------------------- floating toolbar
        toolbar_row = QHBoxLayout()
        toolbar_row.addStretch(1)
        toolbar = QFrame()
        toolbar.setObjectName("viewerToolbar")
        apply_elevation(toolbar, 2)
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(S("space-3"), S("space-2"), S("space-3"), S("space-2"))
        tools.setSpacing(S("space-2"))

        self.btn_fit = Button("Fit", "filter", icon="maximize", size="sm")
        self.btn_fit.setCheckable(True)
        self.btn_fit.setChecked(True)
        self.btn_fit.setToolTip("Fit to window (F)")
        self.btn_fit.clicked.connect(self.set_fit_mode)
        tools.addWidget(self.btn_fit)

        self.btn_zoom_out = IconButton("zoom-out", "Zoom out (−)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        tools.addWidget(self.btn_zoom_out)

        self.zoom_label = QLabel("—")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setMinimumWidth(S("space-8") * 2)
        self.zoom_label.setToolTip("Current zoom level — the arrow keys pan the photo when it is zoomed in")
        theme.enable_tabular(self.zoom_label)
        tools.addWidget(self.zoom_label)

        self.btn_zoom_in = IconButton("zoom-in", "Zoom in (+)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        tools.addWidget(self.btn_zoom_in)

        pan_hint = QLabel("Arrow keys pan")
        pan_hint.setObjectName("panHint")
        theme.apply_role(pan_hint, "small")
        pan_hint.setToolTip("Use the arrow keys to pan the photo when it is zoomed in")
        tools.addWidget(pan_hint)

        self.btn_close = IconButton("x", "Close (Esc)")
        self.btn_close.clicked.connect(self.accept)
        tools.addWidget(self.btn_close)

        toolbar_row.addWidget(toolbar, 0)
        toolbar_row.addStretch(1)
        root_layout.addLayout(toolbar_row)

        # --------------------------------------------------- initial render
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

    # ---------------------------------------------------------------- zoom
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
        self.zoom_label.setText(f"Fit · {pct}%")

    def _render_pixmap(self):
        if not self.full_pixmap or self.full_pixmap.isNull():
            self.image_label.setText("No photo preview available")
            self.image_container.resize(200, 100)
            return

        target_w = max(1, int(round(self.full_pixmap.width() * self.scale_factor)))
        target_h = max(1, int(round(self.full_pixmap.height() * self.scale_factor)))

        scaled = self.full_pixmap.scaled(
            target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.image_container.resize(scaled.size())

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self.is_fit_mode:
            self._apply_fit()

    # ------------------------------------------------------------ keyboard
    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        """``F`` fit, ``+``/``−`` zoom, arrow keys pan; ``Esc`` keeps rejecting."""
        key = event.key()
        if key == Qt.Key.Key_F:
            self.set_fit_mode()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.zoom_out()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) and self._pan(key):
            pass
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def _pan(self, key) -> bool:
        """Scroll by ``PAN_STEP`` when the zoomed photo overflows its viewport."""
        horizontal = self.scroll_area.horizontalScrollBar()
        vertical = self.scroll_area.verticalScrollBar()
        step = self.PAN_STEP
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            if horizontal.maximum() <= 0:
                return False
            horizontal.setValue(horizontal.value() + (-step if key == Qt.Key.Key_Left else step))
            return True
        if vertical.maximum() <= 0:
            return False
        vertical.setValue(vertical.value() + (-step if key == Qt.Key.Key_Up else step))
        return True

    # --------------------------------------------------------- async fetch
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

    def closeEvent(self, event):  # noqa: N802 - Qt API
        self._cleanup_worker()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_worker()
        super().reject()

    def accept(self):
        self._cleanup_worker()
        super().accept()
