import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from desktop.app.ui.photo_viewer import (
    ClickablePhotoLabel,
    PhotoFetchWorker,
    PhotoViewerDialog,
)
from desktop.app.ui.pages.maintenance import MaintenancePage


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def test_photo_fetch_worker_invalid_url(qapp):
    worker = PhotoFetchWorker("not_a_valid_url")
    failed_msgs = []
    worker.failed.connect(failed_msgs.append)
    worker.start()
    worker.wait(1000)
    qapp.processEvents()
    assert len(failed_msgs) == 1
    assert "Invalid" in failed_msgs[0]


def test_photo_fetch_worker_stop(qapp):
    worker = PhotoFetchWorker("https://example.com/photo.jpg")
    worker.stop()
    assert worker._stopped is True
    worker.deleteLater()
    qapp.processEvents()


def test_photo_viewer_dialog_initial_pixmap_and_zoom(qapp):
    pm = QPixmap(400, 300)
    pm.fill(Qt.blue)

    dlg = PhotoViewerDialog(initial_pixmap=pm)
    dlg.show()
    qapp.processEvents()

    assert dlg.full_pixmap is not None
    assert dlg.full_pixmap.width() == 400
    assert dlg.is_fit_mode is True
    assert "Fit" in dlg.zoom_label.text()

    # Zoom in
    dlg.zoom_in()
    assert dlg.is_fit_mode is False
    assert not dlg.btn_fit.isChecked()
    assert "%" in dlg.zoom_label.text()

    # Zoom out repeatedly to reach minimum 25%
    for _ in range(25):
        dlg.zoom_out()
    assert dlg.scale_factor == PhotoViewerDialog.MIN_SCALE
    assert dlg.zoom_label.text() == "25%"

    # Zoom in repeatedly to reach maximum 400%
    for _ in range(25):
        dlg.zoom_in()
    assert dlg.scale_factor == PhotoViewerDialog.MAX_SCALE
    assert dlg.zoom_label.text() == "400%"

    # Return to Fit
    dlg.set_fit_mode()
    assert dlg.is_fit_mode is True
    assert dlg.btn_fit.isChecked()
    assert "Fit" in dlg.zoom_label.text()

    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def test_maintenance_page_photo_clicks_and_states(qapp):
    class FakeStorage:
        def from_(self, bucket):
            return self

        def create_signed_url(self, path, ttl):
            return None

    class FakeClient:
        storage = FakeStorage()

        def table(self, name):
            class FakeTable:
                def select(self, *a, **k):
                    return self
                def order(self, *a, **k):
                    return self
                def execute(self):
                    return type("Resp", (), {"data": []})()
            return FakeTable()

    page = MaintenancePage(FakeClient())
    qapp.processEvents()

    msg_boxes = []
    real_info = QMessageBox.information
    real_exec = PhotoViewerDialog.exec

    def fake_exec(dlg_self):
        dialog_opened.append(True)
        if dlg_self.worker is not None:
            dlg_self.worker.stop()
            dlg_self.worker.wait(2000)

    try:
        from desktop.app.ui.pages import maintenance as maint_mod
        maint_mod.QMessageBox.information = lambda *a: msg_boxes.append(a)
        maint_mod.PhotoViewerDialog.exec = fake_exec

        # Test 1: No ticket selected -> click does nothing
        page.on_photo_clicked()
        assert len(msg_boxes) == 0

        # Test 2: Ticket with NO photo -> shows information dialog
        ticket_no_photo = {"id": "1", "description": "Broken chair", "photo_path": None, "students": {}}
        page.rows = [ticket_no_photo]
        page.table.setRowCount(1)
        page.table.selectRow(0)
        page.show_detail()
        qapp.processEvents()

        assert page.photo_label.text() == "No photo attached by resident"
        page.on_photo_clicked()
        assert len(msg_boxes) == 1
        assert "No photo was attached" in msg_boxes[0][2]

        # Test 3: Ticket with failed photo fetch -> shows informative dialog with no hang
        page._photo_fetch_failed = True
        page._current_pixmap = None
        ticket_photo = {"id": "2", "description": "Water leak", "photo_path": "photos/leak.jpg", "students": {}}
        page.rows = [ticket_photo]
        page.table.selectRow(0)
        # simulate failed state
        page._photo_fetch_failed = True
        page._current_pixmap = None
        page.on_photo_clicked()
        assert len(msg_boxes) == 2
        assert "could not be loaded" in msg_boxes[1][2]

        # Test 4: Ticket with valid photo opens PhotoViewerDialog
        dialog_opened = []
        pm = QPixmap(100, 100)
        pm.fill(Qt.red)
        page._current_pixmap = pm
        page._current_photo_url = "https://example.com/valid.jpg"
        page._photo_fetch_failed = False

        page.on_photo_clicked()
        assert len(dialog_opened) == 1
    finally:
        from desktop.app.ui.pages import maintenance as maint_mod
        maint_mod.QMessageBox.information = real_info
        maint_mod.PhotoViewerDialog.exec = real_exec
        page.close()
        qapp.processEvents()


def test_photo_fetch_worker_and_dialog_full_loaded_swap(qapp):
    import io
    import urllib.request
    from PySide6.QtCore import QBuffer, QIODevice

    pm = QPixmap(200, 150)
    pm.fill(Qt.green)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    raw_bytes = bytes(buf.data())

    class FakeResp:
        def __init__(self, data):
            self.data = io.BytesIO(data)
        def read(self, n=65536):
            return self.data.read(n)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    real_urlopen = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=15: FakeResp(raw_bytes)

    try:
        worker = PhotoFetchWorker("https://example.com/test_image.png")
        loaded_data = []
        worker.loaded.connect(loaded_data.append)
        worker.start()
        worker.wait(3000)
        qapp.processEvents()
        assert len(loaded_data) == 1
        assert loaded_data[0] == raw_bytes
        buf.close()

        small_pm = QPixmap(50, 50)
        dlg = PhotoViewerDialog(initial_pixmap=small_pm)
        dlg.show()
        qapp.processEvents()

        dlg._on_full_loaded(raw_bytes)
        assert dlg.full_pixmap.width() == 200
        assert dlg.full_pixmap.height() == 150
        assert "200 × 150" in dlg.status_label.text()

        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()
    finally:
        urllib.request.urlopen = real_urlopen
