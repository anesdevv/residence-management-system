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
(currently `0.0.1`). Keep it in sync with `MyAppVersion` in
`desktop\installer.iss`.
