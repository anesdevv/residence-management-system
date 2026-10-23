"""Tests for C4: Windows EXE icon, sizes, version resource, and window icon."""

import os
from pathlib import Path
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from desktop.main import _resolve_brand_icon


_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


def test_resivo_ico_exists_and_contains_expected_sizes():
    root = Path(__file__).resolve().parents[2]
    ico_path = root / "desktop" / "assets" / "brand" / "resivo.ico"
    assert ico_path.is_file(), f"ICO file missing at {ico_path}"

    with Image.open(ico_path) as im:
        assert im.format == "ICO"
        sizes = sorted(w for w, _ in im.ico.sizes())
        expected = [16, 24, 32, 48, 64, 128, 256]
        assert sizes == expected, f"Expected sizes {expected}, got {sizes}"


def test_resivo_spec_references_icon_and_version():
    root = Path(__file__).resolve().parents[2]
    spec_path = root / "desktop" / "resivo.spec"
    assert spec_path.is_file()
    spec_content = spec_path.read_text(encoding="utf-8")

    assert "resivo.ico" in spec_content
    assert "version_info.txt" in spec_content
    assert "icon=" in spec_content
    assert "version=" in spec_content


def test_version_info_contains_metadata():
    root = Path(__file__).resolve().parents[2]
    v_path = root / "desktop" / "version_info.txt"
    assert v_path.is_file()
    text = v_path.read_text(encoding="utf-8")

    assert "RÉSIVO" in text or "R\\u00c9SIVO" in text
    assert "Direction des" in text and "Tlemcen" in text
    assert "FileDescription" in text
    assert "ProductName" in text
    assert "CompanyName" in text


def test_app_window_icon_is_valid():
    icon_path = _resolve_brand_icon()
    assert icon_path.is_file()
    icon = QIcon(str(icon_path))
    assert not icon.isNull()
    sizes = [s.width() for s in icon.availableSizes()]
    assert 16 in sizes
    assert 256 in sizes
