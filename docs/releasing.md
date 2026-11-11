# Releasing RÉSIVO Desktop

Everything about a release flows from one number: `__version__` in
`desktop\version.py`. Nothing else in the repository, the installer, or the
PyInstaller spec may hard-code it, and `desktop\tests\test_version_single_source.py`
enforces that.

The running app checks `https://api.github.com/repos/anesdevv/residence-management-system/releases/latest`
(the "latest" release only) once every 24 hours, with no token and no secret.

## 1. Bump the version

Edit exactly one line:

```python
# desktop/version.py
__version__ = "1.0.1"
```

`MAJOR.MINOR.PATCH` only (three numeric components). `VERSION_INFO` is derived
from it, and everything else follows:

| Consumer | How it gets the version |
|---|---|
| Settings / dialogs | `desktop.app.config.APP_VERSION` (re-exported from `desktop.version`) |
| `RESIVO.exe --selftest` | the `version` self-test check |
| Windows EXE version resource | `desktop/resivo.spec` renders `desktop/version_info.txt` (`@MAJOR@`…`@BUILD@`) into the PyInstaller workpath |
| Installer (`Setup-RESIVO-<version>.exe`, Add/Remove Programs) | `tools\release\make_release.ps1` passes `/DMyAppVersion=<version>` to ISCC |
| Update check / download | `desktop.updater` compares against this value |

## 2. Write release notes (optional before building)

Create `docs\release-notes\<version>.md` (for example
`docs\release-notes\1.0.1.md`). English is the primary language; a French
section is welcome, for example:

```markdown
## English

- Fixed the room-change confirmation dialog.

## Français

- Correction de la boîte de confirmation de changement de chambre.
```

If the file is missing, `make_release.ps1` generates a temporary template and
tells you where it is. You can also pass `-NotesFile <path>`.

## 3. Build (one command)

From the repository root, in Windows PowerShell 5.1:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\release\make_release.ps1
```

The script:

1. reads `__version__` from `desktop\version.py` (build fails if it is missing);
2. deletes `build\resivo`, `dist\RESIVO`, `dist\installer`;
3. runs `desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec`
   (the spec renders the Windows version resource from `desktop\version.py`);
4. finds `ISCC.exe` (per-user `%LOCALAPPDATA%\Programs\Inno Setup 6` first, then
   `Program Files (x86)` / `Program Files`) and compiles
   `desktop\installer\resivo.iss` with `/DMyAppVersion=<version>`;
5. verifies `dist\installer\Setup-RESIVO-<version>.exe` exists;
6. writes `dist\installer\SHA256SUMS.txt`;
7. prints the exact `gh release create` command and the manual GitHub steps.

**It never publishes anything.** No tag, no push, no upload.

Useful variants:

```powershell
# Reuse dist\RESIVO and only rebuild the installer + checksums
... make_release.ps1 -SkipBuild

# Custom release notes
... make_release.ps1 -NotesFile docs\release-notes\1.0.1.md
```

## 4. Verify before publishing

```powershell
desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q
dist\RESIVO\RESIVO.exe --selftest
```

`SHA256SUMS.txt` contains one line in `sha256sum` format (uppercase hash, two
spaces, file name):

```
<UPPERCASE_SHA256>  Setup-RESIVO-<version>.exe
```

Confirm it with:

```powershell
Get-Content dist\installer\SHA256SUMS.txt
Get-FileHash dist\installer\Setup-RESIVO-<version>.exe -Algorithm SHA256
```

## 5. Release convention

- **Tag:** `vMAJOR.MINOR.PATCH` — exactly the `version.py` value with a `v`
  prefix (`1.0.1` → `v1.0.1`).
- **Title:** `RÉSIVO vMAJOR.MINOR.PATCH`.
- **Assets:** exactly two files:
  1. `Setup-RESIVO-<version>.exe`
  2. `SHA256SUMS.txt`
- The updater only accepts an asset whose name matches
  `Setup-RESIVO-<x.y.z>.exe`, and only offers a version **strictly newer** than
  the installed one.

Publish with the GitHub CLI (copy the command printed by the script):

```powershell
gh release create v1.0.1 dist\installer\Setup-RESIVO-1.0.1.exe dist\installer\SHA256SUMS.txt --title "RÉSIVO v1.0.1" --notes-file docs\release-notes\1.0.1.md
```

Or use the GitHub website: **Releases → Draft a new release**, choose the tag,
fill the title, upload the two assets, tick **Set as the latest release**, and
publish.

## 6. Testing a build first (pre-release)

Tick **Set as a pre-release** (or `gh release create --prerelease ...`). The
app checks `/releases/latest`, which GitHub does not point at pre-releases, so
a pre-release is invisible to staff installations. This is the safe way to
smoke-test the update flow end to end before promoting a stable release.

## 7. Withdrawing a bad release

Only strictly newer versions are ever offered, so there are two safe options:

1. **Delete the bad release** (Releases → the release → Delete). The updater
   then sees the previous release; installations that already updated stay on
   the bad version and need a repair/reinstall.
2. **Publish a newer fixed version** (recommended): bump `version.py` again
   (for example `1.0.2`), rebuild, and publish. Every installation running the
   bad version will be offered the fix on its next check.

Never re-upload a different binary under an existing version number — checksums,
caches, and installed copies would disagree.

## 8. Secrets

The app carries **no token and no secret**. The update check is an anonymous
call to the public GitHub REST API, downloads come only from GitHub hosts, and
every installer is verified against `SHA256SUMS.txt` before it runs. The only
credentials in the shipped bundle are the public Supabase URL and anon key
(`desktop/resivo.spec` writes a sanitized `.env`), which are safe to distribute
by design.

## 9. Silent update command line

The updater launches the downloaded installer exactly like this:

```
"Setup-RESIVO-<version>.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /SP- /UPDATE=1
```

`/UPDATE=1` makes `resivo.iss` skip the launch checkbox and instead relaunch
`RESIVO.exe --updated` after a successful silent install. `CloseApplications=yes`
lets Inno Setup close the running app; `RestartApplications=no` leaves the
restart to RÉSIVO itself.

## 10. What the updater verifies — and what it does not

Before an installer is allowed to run, the updater checks all of the following:

1. the download URL is HTTPS and its host is one of `github.com`,
   `release-assets.githubusercontent.com` or `objects.githubusercontent.com`;
2. the asset name matches `Setup-RESIVO-<MAJOR>.<MINOR>.<PATCH>.exe` and its
   version is strictly newer than the installed one;
3. the file size matches the GitHub asset metadata and stays under 300 MB;
4. the SHA-256 matches the value in the published `SHA256SUMS.txt`;
5. the file starts with the Windows `MZ` header.

Those checks protect against a corrupted download, a wrong file and a swapped
asset on GitHub. They do **not** protect against a compromised GitHub account or
repository, because the checksum is published in the same release.

### Future work: signed releases

A detached Ed25519 signature (for example `SHA256SUMS.txt.sig` checked against a
public key embedded in `desktop/updater/config.py`) would close that gap. It is
not implemented today because the `cryptography` package is not part of the
desktop bundle; adding it would increase the installer size and needs a key
management and rotation policy first. If it is added later, the signature check
must run before the installer launch and must be enforced for every release.

### Rate limits

The check is anonymous, so GitHub applies the public rate limit per IP. The
updater caches the last answer, checks at most once every 24 hours, and shows a
localized "try again after …" message when GitHub returns a rate-limit response.
Opening the release page manually remains possible at
<https://github.com/anesdevv/residence-management-system/releases>.

