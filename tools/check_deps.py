"""Dependency & bundle completeness scanner for dist/RESIVO."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile


# Core Windows 10/11 system DLLs guaranteed present in %SystemRoot%\System32
_WINDOWS_SYSTEM_DLLS = {
    "advapi32.dll",
    "bcrypt.dll",
    "bcryptprimitives.dll",
    "cfgmgr32.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "d2d1.dll",
    "d3d11.dll",
    "d3d12.dll",
    "d3d9.dll",
    "dbghelp.dll",
    "dnsapi.dll",
    "dwmapi.dll",
    "dwrite.dll",
    "dxgi.dll",
    "gdi32.dll",
    "glu32.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "kernelbase.dll",
    "mpr.dll",
    "msvcp60.dll",
    "msvcrt.dll",
    "ncrypt.dll",
    "netapi32.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "opengl32.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "secur32.dll",
    "setupapi.dll",
    "shcore.dll",
    "shell32.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "uiautomationcore.dll",
    "user32.dll",
    "userenv.dll",
    "uxtheme.dll",
    "version.dll",
    "winhttp.dll",
    "winmm.dll",
    "winspool.drv",
    "wintrust.dll",
    "wldap32.dll",
    "ws2_32.dll",
    "wtsapi32.dll",
    "netutils.dll",
    "srvcli.dll",
    "samcli.dll",
    "authz.dll",
    "dxva2.dll",
    "dcomp.dll",
    "wevtapi.dll",
    "cabinet.dll",
    "imagehlp.dll",
    "msimg32.dll",
    "pdh.dll",
    "profapi.dll",
    "shfolder.dll",
    "sppc.dll",
    "twinapi.appcore.dll",
    "urlmon.dll",
}

_SYSTEM_PREFIXES = (
    "api-ms-win-",
    "ext-ms-win-",
)


def is_windows_system_dll(name_lower: str) -> bool:
    return name_lower in _WINDOWS_SYSTEM_DLLS or name_lower.startswith(_SYSTEM_PREFIXES)


def expected_desktop_modules(repo_root: Path | None = None) -> set[str]:
    """Return every importable ``desktop.*`` module name in the source tree."""
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[1]
    desktop_root = root / "desktop"
    expected: set[str] = set()
    if desktop_root.is_dir():
        for subpkg in ("app", "ui", "auth", "i18n", "platform", "updater"):
            pkg_dir = desktop_root / subpkg
            for py_file in pkg_dir.rglob("*.py"):
                if "__pycache__" in py_file.parts:
                    continue
                rel = py_file.relative_to(root).with_suffix("")
                parts = list(rel.parts)
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                expected.add(".".join(parts))
        expected.add("desktop.version")
    return expected


def find_missing_desktop_modules(bundle_dir: Path) -> list[str]:
    """Return any desktop.* source modules missing from RESIVO.exe's embedded PYZ.pyz."""
    exe_path = bundle_dir / "RESIVO.exe"
    if not exe_path.is_file():
        return ["RESIVO.exe missing"]
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        return []

    arch = CArchiveReader(str(exe_path))
    pyz = arch.open_embedded_archive("PYZ.pyz")
    bundled = set(pyz.toc.keys())
    return sorted(expected_desktop_modules() - bundled)


def scan_bundle(bundle_dir: Path) -> dict:
    if not bundle_dir.is_dir():
        raise FileNotFoundError(f"Bundle directory not found: {bundle_dir}")

    pe_files = sorted(
        list(bundle_dir.rglob("*.exe"))
        + list(bundle_dir.rglob("*.dll"))
        + list(bundle_dir.rglob("*.pyd"))
    )
    bundled_names = {p.name.lower() for p in pe_files}

    non_64bit: list[str] = []
    missing_deps: dict[str, list[str]] = {}
    vc_runtime_found: list[str] = []

    vc_targets = {
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "msvcp140_codecvt_ids.dll",
        "concrt140.dll",
        "vccorlib140.dll",
    }
    for name in sorted(vc_targets):
        if name in bundled_names:
            vc_runtime_found.append(name)

    api_crt_count = sum(1 for n in bundled_names if n.startswith("api-ms-win-crt-"))

    for binary in pe_files:
        rel = str(binary.relative_to(bundle_dir))
        pe = pefile.PE(str(binary), fast_load=True)
        try:
            if pe.FILE_HEADER.Machine != 0x8664:
                non_64bit.append(f"{rel} (machine=0x{pe.FILE_HEADER.Machine:x})")
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
            )
            imports = getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []
            for entry in imports:
                dep = entry.dll.decode("utf-8", errors="replace").lower()
                if dep in bundled_names:
                    continue
                if is_windows_system_dll(dep):
                    continue
                missing_deps.setdefault(dep, []).append(rel)
        finally:
            pe.close()

    internal = bundle_dir / "_internal"
    missing_desktop_modules = find_missing_desktop_modules(bundle_dir)
    checks = {
        "qwindows": (internal / "PySide6" / "plugins" / "platforms" / "qwindows.dll").is_file(),
        "styles": (internal / "PySide6" / "plugins" / "styles" / "qmodernwindowsstyle.dll").is_file(),
        "imageformats_ico": (internal / "PySide6" / "plugins" / "imageformats" / "qico.dll").is_file(),
        "imageformats_jpeg": (internal / "PySide6" / "plugins" / "imageformats" / "qjpeg.dll").is_file(),
        "iconengines_svg": (internal / "PySide6" / "plugins" / "iconengines" / "qsvgicon.dll").is_file(),
        "tls_schannel": (internal / "PySide6" / "plugins" / "tls" / "qschannelbackend.dll").is_file(),
        "qtbase_fr": (internal / "translations" / "qtbase_fr.qm").is_file()
        or (internal / "PySide6" / "translations" / "qtbase_fr.qm").is_file(),
        "i18n_en": (internal / "i18n" / "en.json").is_file(),
        "i18n_fr": (internal / "i18n" / "fr.json").is_file(),
        "certifi_pem": (internal / "certifi" / "cacert.pem").is_file(),
        "fonts_outfit": (internal / "assets" / "fonts" / "Outfit-Bold.ttf").is_file(),
        "fonts_inter": (internal / "assets" / "fonts" / "Inter-Regular.ttf").is_file(),
        "env_next_to_exe": (bundle_dir / ".env").is_file(),
        "desktop_modules_bundled": not missing_desktop_modules,
    }

    return {
        "pe_files_scanned": len(pe_files),
        "non_64bit": non_64bit,
        "missing_non_system_deps": {k: sorted(v) for k, v in sorted(missing_deps.items())},
        "missing_desktop_modules": missing_desktop_modules,
        "vc_runtime_bundled": vc_runtime_found,
        "api_crt_forwarders_bundled": api_crt_count,
        "checks": checks,
    }


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/RESIVO")
    report = scan_bundle(target)
    print(json.dumps(report, indent=2))
    failed = (
        bool(report["non_64bit"])
        or bool(report["missing_non_system_deps"])
        or not all(report["checks"].values())
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
