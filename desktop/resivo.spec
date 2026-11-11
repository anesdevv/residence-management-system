# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).resolve().parent
DESKTOP_DIR = ROOT / "desktop"
ASSETS_DIR = DESKTOP_DIR / "assets"
I18N_DIR = DESKTOP_DIR / "i18n"

# ---------------------------------------------------------------------------
# Build-time sanitized .env (ONLY public SUPABASE_URL + SUPABASE_ANON_KEY)
# ---------------------------------------------------------------------------
def _write_sanitized_env(target_dir: Path) -> Path | None:
    src_candidates = [DESKTOP_DIR / ".env", ROOT / ".env"]
    url = ""
    anon_key = ""
    for src in src_candidates:
        if not src.is_file():
            continue
        for raw_line in src.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if key == "SUPABASE_URL" and not url:
                url = val
            elif key == "SUPABASE_ANON_KEY" and not anon_key:
                anon_key = val
        if url and anon_key:
            break
    if not (url and anon_key):
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / ".env"
    out.write_text(
        f"SUPABASE_URL={url}\nSUPABASE_ANON_KEY={anon_key}\n",
        encoding="utf-8",
    )
    return out


_BUILD_STAGE_DIR = Path(workpath)
_SANITIZED_ENV = _write_sanitized_env(_BUILD_STAGE_DIR)

# ---------------------------------------------------------------------------
# Data files: brand assets, fonts, i18n JSON catalogs, certifi CA, Qt i18n
# ---------------------------------------------------------------------------
datas = [
    (str(ASSETS_DIR), "assets"),
    (str(I18N_DIR / "en.json"), "i18n"),
    (str(I18N_DIR / "fr.json"), "i18n"),
]
datas.extend(collect_data_files("certifi"))
if _SANITIZED_ENV is not None:
    datas.append((str(_SANITIZED_ENV), "."))

# Qt translations (e.g. qtbase_fr.qm) + guaranteed Qt plugin directories
import PySide6  # noqa: E402

_PYSIDE_DIR = Path(PySide6.__file__).resolve().parent
_QT_TRANS_FR = _PYSIDE_DIR / "translations" / "qtbase_fr.qm"
if _QT_TRANS_FR.is_file():
    datas.append((str(_QT_TRANS_FR), "translations"))

_QT_PLUGINS_DIR = _PYSIDE_DIR / "plugins"
binaries = []
for _plugin_sub in ("platforms", "styles", "imageformats", "iconengines", "tls"):
    _pdir = _QT_PLUGINS_DIR / _plugin_sub
    if _pdir.is_dir():
        for _dll in sorted(_pdir.glob("*.dll")):
            binaries.append((str(_dll), f"PySide6/plugins/{_plugin_sub}"))

# Explicitly collect VC++ 2015-2022 runtime + UCRT forwarder DLLs so the bundle
# runs on a clean Windows 10/11 PC with no VC++ redistributable installed.
_VC_RUNTIME_DLLS = (
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_codecvt_ids.dll",
    "concrt140.dll",
    "vccorlib140.dll",
)
_VC_SEARCH_DIRS = [
    _PYSIDE_DIR,
    Path(sys.base_prefix),
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32",
]
for _vc_name in _VC_RUNTIME_DLLS:
    for _sdir in _VC_SEARCH_DIRS:
        _cand = _sdir / _vc_name
        if _cand.is_file():
            binaries.append((str(_cand), "."))
            break

_DOWNLEVEL_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "downlevel"
if _DOWNLEVEL_DIR.is_dir():
    for _crt_dll in sorted(_DOWNLEVEL_DIR.glob("api-ms-win-crt-*.dll")):
        binaries.append((str(_crt_dll), "."))

# ---------------------------------------------------------------------------
# Hidden imports (explicit coverage so nothing depends on external Python)
# ---------------------------------------------------------------------------
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    "openpyxl",
    "et_xmlfile",
    "supabase",
    "postgrest",
    "gotrue",
    "realtime",
    "storage3",
    "supafunc",
    "httpx",
    "httpcore",
    "h11",
    "anyio",
    "anyio._backends._asyncio",
    "sniffio",
    "idna",
    "websockets",
    "pydantic",
    "pydantic_core",
    "certifi",
    "dotenv",
    "app.client",
    "app.coalescer",
    "app.config",
    "app.logging_setup",
    "app.selftest",
    "app.startup_debug",
    "app.timeouts",
    "app.tls",
    "app.ui.close_policy",
    "app.ui.components",
    "app.ui.icons",
    "app.ui.infocard",
    "app.ui.live_sync",
    "app.ui.login_window",
    "app.ui.main_window",
    "app.ui.notifications",
    "app.ui.photo_viewer",
    "app.ui.residence_dialogs",
    "app.ui.resource",
    "app.ui.stepper",
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
    "desktop.auth.session_store",
    "desktop.i18n",
    "desktop.platform.autostart",
    "desktop.platform.win32_compat",
]
hiddenimports.extend(collect_submodules("pydantic_core"))
hiddenimports.extend(collect_submodules("websockets"))

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
    # Unused PySide6 / Qt6 modules (keep QtCore, QtGui, QtWidgets, QtSvg, QtNetwork)
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
    binaries=binaries,
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

# Prune unused heavy Qt binaries while preserving Qt6Network.dll (required by TLS plugins)
# and VC++/UCRT runtime DLLs.
_EXCLUDE_BINARY_NAMES = {
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmeta.dll",
    "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll",
    "qt6pdf.dll",
    "qt6pdfwidgets.dll",
    "qpdf.dll",
    "qt6opengl.dll",
    "qt6virtualkeyboard.dll",
    "qtvirtualkeyboardplugin.dll",
    "qt6labsstylekit.dll",
    "qt6quickcontrols2.dll",
    "qt6quicktemplates2.dll",
    "d3dcompiler_47.dll",
}

_seen_targets: set[str] = set()
_deduped_binaries = []
for item in a.binaries:
    dest_key = item[0].replace("\\", "/").lower()
    if Path(item[0]).name.lower() in _EXCLUDE_BINARY_NAMES:
        continue
    if any(k in item[0].lower() for k in ("numpy", "scipy", "openblas", "lxml")):
        continue
    if dest_key in _seen_targets:
        continue
    _seen_targets.add(dest_key)
    _deduped_binaries.append(item)
a.binaries = _deduped_binaries

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

# Also place an editable sanitized .env directly beside RESIVO.exe (only URL + anon key).
if _SANITIZED_ENV is not None:
    _dist_env = Path(DISTPATH) / "RESIVO" / ".env"
    _dist_env.parent.mkdir(parents=True, exist_ok=True)
    _dist_env.write_text(_SANITIZED_ENV.read_text(encoding="utf-8"), encoding="utf-8")
