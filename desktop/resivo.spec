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
]

a = Analysis(
    [str(DESKTOP_DIR / "main.py")],
    pathex=[str(DESKTOP_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_DIR / "brand" / "resivo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RESIVO",
)
