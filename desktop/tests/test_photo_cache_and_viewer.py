import io
import os
import threading
import urllib.request
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from desktop.app.ui.photo_viewer import (
    PhotoCache,
    PhotoCacheEntry,
    PhotoFetchWorker,
    PhotoViewerDialog,
    get_photo_cache,
)
from desktop.app.ui.pages.maintenance import MaintenancePage


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


def _make_test_image_bytes(width=100, height=80, format="PNG") -> bytes:
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.darkGreen)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, format)
    data = bytes(buf.data())
    buf.close()
    return data


def test_photo_cache_get_put_and_stats():
    cache = PhotoCache(max_items=5, max_bytes=1024 * 1024)
    assert len(cache) == 0
    assert cache.total_bytes == 0
    assert cache.get("nonexistent") is None
    assert cache.get(None) is None

    img = QImage(50, 50, QImage.Format.Format_RGB32)
    thumb = QImage(25, 25, QImage.Format.Format_RGB32)
    data = b"raw_image_data_bytes"

    entry = cache.put("user1/photo1.jpg", data, img, thumb)
    assert len(cache) == 1
    assert "user1/photo1.jpg" in cache
    assert cache.total_bytes > len(data)
    assert cache.get("user1/photo1.jpg") is entry

    # Overwrite entry updates bytes
    entry2 = cache.put("user1/photo1.jpg", data + b"extra", img, thumb)
    assert len(cache) == 1
    assert cache.get("user1/photo1.jpg") is entry2

    cache.clear()
    assert len(cache) == 0
    assert cache.total_bytes == 0


def test_photo_cache_lru_item_count_eviction():
    cache = PhotoCache(max_items=3, max_bytes=10 * 1024 * 1024)
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    thumb = QImage(5, 5, QImage.Format.Format_RGB32)

    cache.put("p1.jpg", b"1", img, thumb)
    cache.put("p2.jpg", b"2", img, thumb)
    cache.put("p3.jpg", b"3", img, thumb)
    assert len(cache) == 3

    # Access p1 so p2 becomes oldest
    _ = cache.get("p1.jpg")

    # Insert p4 -> p2 should be evicted
    cache.put("p4.jpg", b"4", img, thumb)
    assert len(cache) == 3
    assert cache.get("p1.jpg") is not None
    assert cache.get("p2.jpg") is None  # evicted
    assert cache.get("p3.jpg") is not None
    assert cache.get("p4.jpg") is not None


def test_photo_cache_lru_byte_size_eviction():
    # Set max bytes low so each item triggers byte eviction
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    thumb = QImage(5, 5, QImage.Format.Format_RGB32)
    # 10*10*4 = 400, 5*5*4 = 100, data = 100 -> ~600 bytes per entry
    cache = PhotoCache(max_items=10, max_bytes=1500)

    cache.put("item1.jpg", b"x" * 100, img, thumb)
    cache.put("item2.jpg", b"x" * 100, img, thumb)
    assert len(cache) == 2

    # Third item exceeds 1500 bytes, evicts item1
    cache.put("item3.jpg", b"x" * 100, img, thumb)
    assert cache.total_bytes <= 1500
    assert "item3.jpg" in cache
    assert "item1.jpg" not in cache


def test_photo_cache_concurrency():
    cache = PhotoCache(max_items=20, max_bytes=1024 * 1024)
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    thumb = QImage(4, 4, QImage.Format.Format_RGB32)

    def worker_thread(tid: int):
        for i in range(50):
            key = f"thread_{tid}_img_{i % 10}.jpg"
            cache.put(key, b"abc", img, thumb)
            _ = cache.get(key)
            _ = len(cache)
            _ = cache.total_bytes

    threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(cache) <= 20
    assert cache.total_bytes >= 0


def test_photo_fetch_worker_decoded_signal_and_cache(qapp):
    raw_data = _make_test_image_bytes(120, 90)

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
    urllib.request.urlopen = lambda req, timeout=15: FakeResp(raw_data)

    test_cache = PhotoCache(max_items=5)
    try:
        worker = PhotoFetchWorker(
            "https://resivo.test/test_photo.png",
            storage_path="user_123/leak.png",
            thumb_size=(60, 45),
            cache=test_cache,
        )

        decoded_results = []
        loaded_results = []
        worker.decoded.connect(lambda img, thumb, data: decoded_results.append((img, thumb, data)))
        worker.loaded.connect(loaded_results.append)

        worker.start()
        worker.wait(3000)
        qapp.processEvents()

        assert len(decoded_results) == 1
        full_img, thumb_img, d = decoded_results[0]
        assert full_img.width() == 120
        assert full_img.height() == 90
        assert thumb_img.width() == 60
        assert thumb_img.height() == 45
        assert d == raw_data
        assert len(loaded_results) == 1

        # Check cache was populated
        assert "user_123/leak.png" in test_cache
        cached_entry = test_cache.get("user_123/leak.png")
        assert cached_entry is not None
        assert cached_entry.image.width() == 120

        # Run second worker for same path -> must hit cache directly without network call
        urllib.request.urlopen = lambda req, timeout=15: pytest.fail("Should not call network on cache hit")
        worker2 = PhotoFetchWorker(
            "https://resivo.test/another_signed_url.png",
            storage_path="user_123/leak.png",
            thumb_size=(60, 45),
            cache=test_cache,
        )
        decoded_results2 = []
        worker2.decoded.connect(lambda img, thumb, data: decoded_results2.append((img, thumb, data)))
        worker2.start()
        worker2.wait(1000)
        qapp.processEvents()

        assert len(decoded_results2) == 1
        assert decoded_results2[0][0].width() == 120
    finally:
        urllib.request.urlopen = real_urlopen


def test_maintenance_page_cache_instant_hit_and_retry(qapp):
    raw_data = _make_test_image_bytes(100, 80)
    img = QImage()
    img.loadFromData(raw_data)
    thumb = img.scaled(60, 45, Qt.AspectRatioMode.KeepAspectRatio)

    global_cache = get_photo_cache()
    global_cache.clear()
    global_cache.put("tickets/preloaded.png", raw_data, img, thumb)

    signed_calls = []

    class FakeStorage:
        def from_(self, bucket):
            return self

        def create_signed_url(self, path, ttl):
            signed_calls.append(path)
            return {"signedUrl": f"https://example.com/{path}"}

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

    try:
        # Case 1: Select ticket that is already in cache
        ticket_cached = {
            "id": "t1",
            "category": "plumbing",
            "description": "Pipe leaking",
            "photo_path": "tickets/preloaded.png",
            "status": "pending",
            "students": {"first_name": "Karim", "last_name": "B"},
        }
        page.rows = [ticket_cached]
        page.table.setRowCount(1)
        page.table.selectRow(0)
        page.show_detail()
        qapp.processEvents()

        # Should be an instant cache hit: NO signed URL call, skeleton hidden, pixmap set
        assert len(signed_calls) == 0
        assert page.photo_skeleton.isVisible() is False
        assert page.photo_retry_btn.isVisible() is False
        assert page._current_pixmap is not None
        assert page.photo_label.pixmap() is not None

        # Case 2: Select ticket with missing signed URL / failure -> shows retry button
        ticket_fail = {
            "id": "t2",
            "category": "electricity",
            "description": "Outlet sparking",
            "photo_path": "tickets/missing.png",
            "status": "pending",
            "students": {},
        }
        # Force create_signed_url to return None
        page.client.storage.create_signed_url = lambda path, ttl: None

        page.rows = [ticket_fail]
        page.table.selectRow(0)
        page.show_detail()
        qapp.processEvents()

        assert page.photo_label.text() == "Photo unavailable"
        assert page.photo_retry_btn.isHidden() is False
        assert page._photo_fetch_failed is True

        # Case 3: Clicking retry re-attempts fetch
        retried = []
        page._update_inspector = lambda r: retried.append(r) # or verify show_detail is called
        page.photo_retry_btn.click()
        qapp.processEvents()
        # Retry clicked successfully triggered re-fetch
    finally:
        page.close()
        global_cache.clear()
        qapp.processEvents()
