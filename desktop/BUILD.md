# RÉSIVO desktop — build & run

All commands are run from the repository root (the folder containing `desktop\`).

## Run the test suite

```powershell
desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q
```

The suite runs with Qt's offscreen platform and mocked Supabase clients; it
does not need network access.

## Build the Windows executable

Install the build-only tool once (it is not a runtime dependency):

```powershell
desktop\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
```

Then build:

```powershell
desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec
```

Output:

```text
dist\RESIVO\RESIVO.exe
```

The folder (`dist\RESIVO\`) is self-contained. The optional installer is built
with Inno Setup from `desktop\installer.iss` and ships that folder's contents.

### Distribution Mode & Optimization Strategy

1. **Distribution Mode**: Packaged as a folder directory (`onedir`) via PyInstaller's `COLLECT`.
   - **Why `onedir` instead of `onefile`**: In `onefile` mode, Windows must decompress the entire archive into a temporary `%TEMP%\_MEIxxxxxx` directory on every single launch, adding 3-5 seconds of disk I/O and CPU overhead. In `onedir` mode, binaries are mapped directly into virtual memory, allowing rapid cold-start (~1.9 s).
2. **UPX Compression**: Set to `upx = False` per project policy.
   - UPX-compressed executables on Windows frequently trigger antivirus heuristic false positives and incur a decompression CPU cost on process startup. Without UPX, the binary executes cleanly with standard OS paging.
3. **Module & Binary Exclusion**:
   - `desktop/resivo.spec` strictly excludes unused standard libraries (`tkinter`, `unittest`, `pydoc`, `test`, `pytest`) and large third-party math packages accidentally pulled in by virtual environment tooling (`numpy`, `scipy`, `matplotlib`, `pandas`, `lxml`).
   - All unused Qt6 submodules (such as `QtWebEngine`, `Qt3D`, `QtQuick`, `QtQml`, `QtMultimedia`, `QtPdf`, `QtSql`, `QtCharts`) are excluded, and extraneous DLLs (e.g., `Qt6Quick.dll`, `Qt6Qml.dll`, `Qt6Pdf.dll`, `openblas`) are pruned in the binary collection stage.
   - All necessary components (`QtWidgets`, `QtGui`, `QtCore`, `QtSvg`, platform plugins, styles, image formats, `openpyxl`, and `supabase`/`httpx`) are fully preserved.

### Windows Icon Caching Note
Windows caches executable icons aggressively in `%LocalAppData%\IconCache.db`. After
rebuilding `RESIVO.exe`, if Explorer or Task Manager still displays an old or generic icon:
1. Rename the executable temporarily (e.g. `RESIVO_test.exe`), or
2. Run `ie4uinit.exe -show` in PowerShell / Command Prompt, or
3. Restart Windows Explorer (`Stop-Process -Name explorer -Force`).

The spec bundles `assets\` and the repository-root `.env` (when present) as the
packaged fallback. It intentionally does **not** bundle `mcp/.env`.

## Configuration file placement

At runtime the app reads configuration in this order:

1. `.env` next to `RESIVO.exe` — `dist\RESIVO\.env` for the build above.
2. Bundled `.env` inside `_MEIPASS` (the repository-root file captured at build
   time).
3. Development only: `desktop\.env`, then the repository-root `.env`.

To point a deployment at another project, place this file next to the EXE:

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<public-anon-key>
```

Only the public anon key belongs here. Never put a service-role key in the
desktop app or in the build.

Use `SUPABASE_URL` and `SUPABASE_ANON_KEY` exactly. If either is missing or the
URL is not a valid `http(s)` URL, the app shows a configuration error before the
login window and exits non-zero (the message never includes key values).

## Log file

The rotating log lives at:

```text
%APPDATA%\RESIVO\logs\app.log
```

Set `RESIVO_DATA_DIR` to override the base directory (useful for a portable or
test run). If an unexpected exception occurs, the error dialog provides an
**Open log folder** button to access logs directly.

## Windows Autostart & Startup Settings

RÉSIVO provides an opt-in "Start RÉSIVO when Windows starts" switch in **Settings → General**.
- **Per-User Registry Key**: Writes the quoted executable path and `--autostart` to `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` under value `"RESIVO"`. No administrator rights or elevated privileges are required.
- **Windows Startup Settings**: Reads `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run` to respect user toggles made directly in Task Manager > Startup apps or Windows Settings. Turning the switch ON automatically clears any disabled flag.
- **Single Instance & Minimized Launch**: Launches with `--autostart` exit silently if another copy of RÉSIVO is already running (guarded via `QLockFile`). When "Start minimized to the taskbar" is enabled, both the login window and subsequent main console window open minimized.
- **Moved Executable Handling**: Normal launches verify the registered Run key path and repair it automatically if the executable was moved or reinstalled.
- **Uninstallation**: When using the Inno Setup uninstaller (`desktop\installer.iss`), registry entries under `Run` and `StartupApproved\Run` are automatically deleted. For portable folder installations, turning the switch OFF in Settings before deleting the folder cleanly removes the registry value.

## Developer-mode MCP token

The local MCP server token lives in `mcp\.env` (`MCP_AUTH_TOKEN=...`) and is
**not** bundled: it is a secret. To show it in Settings → Developer mode for a
packaged build, place the file next to the EXE:

```text
dist\RESIVO\mcp\.env
```

```dotenv
MCP_AUTH_TOKEN=<token>
```

In development the app reads the repository's `mcp\.env` directly. If the file
is absent, Settings keeps the existing "Token not found — check mcp/.env."
message.

## Version

`APP_VERSION` in `desktop\app\config.py` is the single application version
(currently `0.1.0`). Keep it in sync with `MyAppVersion` in
`desktop\installer.iss` and `desktop\version_info.txt`.
