# RÉSIVO desktop — build & distribution guide

All commands run from the repository root (the folder containing `desktop\`).
Builds target **64-bit Windows 10 (21H2+) and Windows 11** with zero external
runtime prerequisites on the user's PC (no Python, no VC++ Redistributable,
no .NET, no Qt installer, no internet downloads during install).

## 1. Run the test suite

```powershell
desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

## 2. Clean & build the zero-prerequisite release (recommended order)

### Step A — Clean previous build & dist folders

```powershell
Remove-Item -Recurse -Force build\resivo, dist\RESIVO, dist\installer -ErrorAction SilentlyContinue
Remove-Item -Force dist\RESIVO-*-portable-win64.zip -ErrorAction SilentlyContinue
```

### Step B — Build the PyInstaller `onedir` bundle

`pyinstaller==6.22.3` is a build-time dependency only (`desktop\.venv`):

```powershell
desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec
```

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

### Step D — Build the single-file Inno Setup installer

If Inno Setup 6 is not installed on the build PC, install it once (build PC only; target PCs never need Inno Setup):

```powershell
winget install --id JRSoftware.InnoSetup -e
```

Compile `desktop\installer\resivo.iss`:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" desktop\installer\resivo.iss
```

If installed system-wide instead of per-user, run `"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" desktop\installer\resivo.iss`.

Output: `dist\installer\Setup-RESIVO-0.1.0.exe` (per-user `%LOCALAPPDATA%\Programs\RESIVO`, no admin rights required, 64-bit Windows 10+ check, English/French installer UI, optional unchecked autostart task, clean uninstaller).

### Step E — Build the portable zip fallback

```powershell
Compress-Archive -Path dist\RESIVO\* -DestinationPath dist\RESIVO-0.1.0-portable-win64.zip -Force
```

Unzipping anywhere writable (for example `Desktop\RESIVO` or `%LOCALAPPDATA%\Programs\RESIVO`) and running `RESIVO.exe` gives the exact same zero-prerequisite behavior.

### Step F — Record SHA-256 checksums

```powershell
Get-FileHash dist\installer\Setup-RESIVO-0.1.0.exe, dist\RESIVO-0.1.0-portable-win64.zip -Algorithm SHA256 | Format-Table Algorithm, Hash, Path -AutoSize
```

### Final Release Artifacts & SHA-256 Checksums (`v0.1.0`)

| Artifact | Size (bytes) | SHA-256 |
|---|---|---|
| `dist\installer\Setup-RESIVO-0.1.0.exe` | `37651817` | `08BD578B8449CB12A44D4E0428546D661AD273BA8A9AB67F2E2140F6EABD7294` |
| `dist\RESIVO-0.1.0-portable-win64.zip` | `49928965` | `CEBEFCA62B34DCD957DB1BA5EC62291A6EA0836A7740BC97E34F4F99E04A06B7` |

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
   Start-Process "$env:USERPROFILE\Desktop\RESIVO-Release\installer\Setup-RESIVO-0.1.0.exe" -Wait
   & "$env:LOCALAPPDATA\Programs\RESIVO\RESIVO.exe" --selftest
   ```
4. Launch **RÉSIVO** from the Start Menu and confirm login UI, fonts, French/English switch, tray notifications, and connection all work cleanly.

---

## Distribution & Target PC Notes

### Distribution strategy (`onedir`, `upx=False`)
- Packaged as `onedir` (not `onefile`) so startup skips temporary `%TEMP%\_MEI*` unpacking and avoids heuristic antivirus triggers.
- `upx=False` eliminates UPX false-positive antivirus flags and startup decompression latency.

### Windows SmartScreen & downloaded ZIP unblocking (target PC)
1. **Unblock downloaded ZIP (before extracting)**: Right-click `RESIVO-0.1.0-portable-win64.zip` -> **Properties** -> check **Unblock** (at the bottom next to Security) -> **OK**, or extract cleanly after unblocking.
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
Keep `APP_VERSION` in `desktop\app\config.py` (`0.1.0`) synchronized with `MyAppVersion` in `desktop\installer\resivo.iss` and `desktop\version_info.txt`.
