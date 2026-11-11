# RÉSIVO desktop — build & distribution guide

All commands run from the repository root (the folder containing `desktop\`).
Builds target **64-bit Windows 10 (21H2+) and Windows 11** with zero external
runtime prerequisites on the user's PC (no Python, no VC++ Redistributable,
no .NET, no Qt installer, no internet downloads during install).

## 1. Run the test suite

```powershell
desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

## 2. Build the zero-prerequisite release

`desktop\version.py` is the only source of truth for the version. One command
builds the bundle, compiles the installer, and writes the checksums — without
publishing anything:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\release\make_release.ps1
```

The script prints the exact `gh release create v<version> ...` command; publishing
is a deliberate human step. Full procedure: [docs\releasing.md](../docs/releasing.md).

The manual equivalent is below (useful when debugging the build).

### Step A — Clean previous build & dist folders

```powershell
Remove-Item -Recurse -Force build\resivo, dist\RESIVO, dist\installer -ErrorAction SilentlyContinue
```

### Step B — Build the PyInstaller `onedir` bundle

`pyinstaller==6.22.3` is a build-time dependency only (`desktop\.venv`):

```powershell
desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec
```

`desktop\resivo.spec` reads `__version__` from `desktop\version.py`, renders the
`desktop\version_info.txt` template (`@MAJOR@`/`@MINOR@`/`@PATCH@`/`@BUILD@`)
into the PyInstaller workpath, and stamps that generated file into `RESIVO.exe`.

Outputs `dist\RESIVO\RESIVO.exe` plus `_internal\` containing:
- VC++ 2015–2022 runtime DLLs (`vcruntime140.dll`, `vcruntime140_1.dll`, `msvcp140*.dll`, `concrt140.dll`, `vccorlib140.dll`) and UCRT forwarders (`api-ms-win-crt-*.dll`)
- Qt6 Core/Gui/Widgets/Svg/Network + plugins (`platforms\qwindows.dll`, `styles`, `imageformats`, `iconengines`, `tls\qschannelbackend.dll`) + `translations\qtbase_fr.qm`
- `certifi\cacert.pem` TLS CA bundle, `i18n\{en,fr}.json`, bundled `Outfit`/`Inter` fonts, icons, and brand graphics
- Sanitized `.env` (`SUPABASE_URL` and `SUPABASE_ANON_KEY` only — never secrets) next to `RESIVO.exe`

### Step C — Verify DLL dependencies & run `--selftest`

```powershell
desktop\.venv\Scripts\python.exe tools\check_deps.py dist\RESIVO
dist\RESIVO\RESIVO.exe --selftest
```

`--selftest` reports the packaged version as its first check, so it doubles as a
single-source-of-truth smoke test.

### Step D — Build the single-file Inno Setup installer

If Inno Setup 6 is not installed on the build PC, install it once (build PC only; target PCs never need Inno Setup):

```powershell
winget install --id JRSoftware.InnoSetup -e
```

`desktop\installer\resivo.iss` no longer defines a version: it aborts unless
`MyAppVersion` is provided. Pass the value from `desktop\version.py`:

```powershell
$version = (Select-String -Path desktop\version.py -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" "/DMyAppVersion=$version" desktop\installer\resivo.iss
```

If installed system-wide instead of per-user, run the same command with
`"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"`.

Output: `dist\installer\Setup-RESIVO-<version>.exe` (per-user `%LOCALAPPDATA%\Programs\RESIVO`, no admin rights required, 64-bit Windows 10+ check, English/French installer UI, optional unchecked autostart task, clean uninstaller).

### Step E — Record the release checksum

The release convention is exactly two assets: the installer and
`SHA256SUMS.txt` (uppercase hash, **two spaces**, file name):

```powershell
$hash = (Get-FileHash "dist\installer\Setup-RESIVO-$version.exe" -Algorithm SHA256).Hash.ToUpperInvariant()
"$hash  Setup-RESIVO-$version.exe" | Set-Content -Encoding ASCII dist\installer\SHA256SUMS.txt
```

Never paste a hash into this document: it changes with every build.
`tools\release\make_release.ps1` writes this file for you.

### Step F — Publish (manual)

Follow [docs\releasing.md](../docs/releasing.md): tag `vMAJOR.MINOR.PATCH`, then
upload exactly `Setup-RESIVO-<version>.exe` and `SHA256SUMS.txt`.

### Optional local portable fallback (not a release asset)

```powershell
Compress-Archive -Path dist\RESIVO\* -DestinationPath "dist\RESIVO-$version-portable-win64.zip" -Force
```

Unzipping anywhere writable (for example `Desktop\RESIVO` or `%LOCALAPPDATA%\Programs\RESIVO`) and running `RESIVO.exe` gives the exact same zero-prerequisite behavior.

### Clean-Machine Verification in Windows Sandbox

Windows Sandbox launches a fresh Windows desktop with zero Python, VC++ Redistributable, or development tools. On Windows 10/11 Pro, Enterprise, or Education (if Sandbox is not enabled yet):

1. Enable the feature once in an elevated PowerShell and reboot:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All
   ```
2. Double-click `desktop\installer\resivo-sandbox.wsb` (or run `WindowsSandbox.exe desktop\installer\resivo-sandbox.wsb`).
3. Inside the Sandbox terminal:
   ```powershell
   cd "$env:USERPROFILE\Desktop\RESIVO-Tools"
   powershell -NoProfile -ExecutionPolicy Bypass -File .\preflight.ps1
   $setup = Get-ChildItem "$env:USERPROFILE\Desktop\RESIVO-Release\installer\Setup-RESIVO-*.exe" | Select-Object -First 1
   Start-Process $setup.FullName -Wait
   & "$env:LOCALAPPDATA\Programs\RESIVO\RESIVO.exe" --selftest
   ```
4. Launch **RÉSIVO** from the Start Menu and confirm login UI, fonts, French/English switch, tray notifications, and connection all work cleanly.

---

## Distribution & Target PC Notes

### Distribution strategy (`onedir`, `upx=False`)
- Packaged as `onedir` (not `onefile`) so startup skips temporary `%TEMP%\_MEI*` unpacking and avoids heuristic antivirus triggers.
- `upx=False` eliminates UPX false-positive antivirus flags and startup decompression latency.

### Windows SmartScreen & downloaded ZIP unblocking (target PC)
1. **Unblock downloaded ZIP (before extracting)**: Right-click `RESIVO-<version>-portable-win64.zip` -> **Properties** -> check **Unblock** (at the bottom next to Security) -> **OK**, or extract cleanly after unblocking.
2. **SmartScreen prompt on unsigned EXE / installer**: Click **More info** -> **Run anyway**.
3. Run `tools\preflight.ps1` on the target PC before or during troubleshooting:
   - Right-click `tools\preflight.ps1` -> **Run with PowerShell**, or run:
     ```powershell
     powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\preflight.ps1
     ```

### Windows system proxy & configuration placement
- RÉSIVO uses `httpx` (`trust_env=True`) and `urllib` (`create_ssl_context()` backed by bundled `certifi\cacert.pem`), which automatically honor Windows Internet Settings proxy configuration as well as `HTTP_PROXY`/`HTTPS_PROXY` environment variables.
- Configuration search order at runtime:
  1. `.env` next to `RESIVO.exe` (`SUPABASE_URL` and public `SUPABASE_ANON_KEY` only — editable without rebuilding)
  2. Bundled `.env` inside `_internal\` (`_MEIPASS`)
  3. Development only: `desktop\.env`, then repository root `.env`

### Per-user writable locations (never writes beside `RESIVO.exe` or `Program Files`)
- Rotating logs: `%APPDATA%\RESIVO\logs\app.log` (fallback `%TEMP%\RESIVO\logs\app.log`, override `RESIVO_DATA_DIR`)
- Single-instance lock: `%APPDATA%\RESIVO\resivo.lock`
- Encrypted session token: `%LOCALAPPDATA%\RESIVO\session\session.bin` (DPAPI bound to logon session)
- User preferences: `HKCU\Software\RESIVO\StaffConsole`
- Autostart entry (when enabled): `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (`RESIVO`)

### Developer-mode MCP token
`mcp\.env` (`MCP_AUTH_TOKEN=...`) is intentionally **never** bundled. For developer-mode inspection in a packaged install, place it manually beside `RESIVO.exe` (`<install_dir>\mcp\.env`).

### Version alignment
`desktop\version.py` (`__version__`) is the **only** place a version number may
appear. Everything else derives from it:

- `desktop\app\config.py` re-exports it as `APP_VERSION`.
- `desktop\version_info.txt` is a template (`@MAJOR@`/`@MINOR@`/`@PATCH@`/`@BUILD@`)
  rendered by `desktop\resivo.spec` at build time.
- `desktop\installer\resivo.iss` refuses to compile without `/DMyAppVersion=<version>`;
  `tools\release\make_release.ps1` supplies it.
- `RESIVO.exe --selftest` and the in-app updater read the same value.

To ship a release, edit `desktop\version.py` and run the release script — never
edit the installer or the version-info template. See [docs\releasing.md](../docs/releasing.md).
