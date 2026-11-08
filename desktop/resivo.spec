# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).resolve().parent
DESKTOP_DIR = ROOT / "desktop"
ASSETS_DIR = DESKTOP_DIR / "assets"

datas = [
    (str(ASSETS_DIR), "assets"),
]
if (ROOT / ".env").is_file():
    datas.append((str(ROOT / ".env"), "."))

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "openpyxl",
    "supabase",
    "postgrest",
    "gotrue",
    "realtime",
    "storage3",
    "websockets",
    "dotenv",
    "app.client",
    "app.config",
    "app.ui.live_sync",
    "app.logging_setup",
    "app.ui.components",
    "app.ui.icons",
    "app.ui.infocard",
    "app.ui.login_window",
    "app.ui.main_window",
    "app.ui.photo_viewer",
    "app.ui.tasks",
    "app.ui.theme",
    "app.ui.pages.maintenance",
    "app.ui.pages.official_list",
    "app.ui.pages.overview",
    "app.ui.pages.pending",
    "app.ui.pages.residents",
    "app.ui.pages.room_changes",
    "app.ui.pages.rooms",
    "app.ui.pages.settings",
    "app.ui.pages.staff_accounts",
    "app.importers.official_list",
    "desktop.platform.autostart",
]

excludes = [
    # Standard library unused modules
    "tkinter",
    "unittest",
    "pydoc",
    "test",
    # Test-only / build-only packages
    "pytest",
    "PIL",
    "Pillow",
    "numpy",
    "scipy",
    "lxml",
    "matplotlib",
    "pandas",
    # Unused PySide6 / Qt6 modules (keep QtCore, QtGui, QtWidgets, QtSvg)
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngine",
    "PySide6.QtWebView",
    "PySide6.QtWebChannel",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2",
    "PySide6.QtQml",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtHttpServer",
]

a = Analysis(
    [str(DESKTOP_DIR / "main.py")],
    pathex=[str(ROOT), str(DESKTOP_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Prune unused Qt binaries and third-party libs collected automatically by hooks
_EXCLUDE_BINARY_NAMES = {
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmodels.dll",
    "qt6pdf.dll",
    "qt6pdfwidgets.dll",
    "qt6opengl.dll",
    "qt6network.dll",
    "qt6virtualkeyboard.dll",
    "qt6labsstylekit.dll",
    "qt6quickcontrols2.dll",
    "qt6quicktemplates2.dll",
    "d3dcompiler_47.dll",
}

a.binaries = [
    item for item in a.binaries
    if Path(item[0]).name.lower() not in _EXCLUDE_BINARY_NAMES
    and not any(k in item[0].lower() for k in ("numpy", "scipy", "openblas", "lxml"))
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RESIVO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_DIR / "brand" / "resivo.ico"),
    version=str(DESKTOP_DIR / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RESIVO",
)
