#Requires -Version 5.1
<#
.SYNOPSIS
    Build and package the RESIVO desktop release. Publishes nothing.

.DESCRIPTION
    Single entry point for a release build:

      1. reads the version from desktop\version.py (the only source of truth),
      2. cleans build\resivo, dist\RESIVO and dist\installer,
      3. builds the PyInstaller onedir bundle (desktop\resivo.spec renders the
         Windows version resource from desktop\version.py),
      4. compiles desktop\installer\resivo.iss with /DMyAppVersion=<version>,
      5. verifies dist\installer\Setup-RESIVO-<version>.exe exists,
      6. writes dist\installer\SHA256SUMS.txt,
      7. prints the exact "gh release create" command and the manual GitHub
         website steps.

    This script NEVER tags, pushes, uploads, or publishes anything. Publishing
    is a deliberate human action (see docs\releasing.md).

.PARAMETER SkipBuild
    Reuse the existing dist\RESIVO bundle; only compile the installer and
    refresh the checksums.

.PARAMETER NotesFile
    Release notes file used in the printed publish command. Defaults to
    docs\release-notes\<version>.md when it exists, otherwise a generated
    temporary template.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\release\make_release.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\release\make_release.ps1 -SkipBuild
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [string]$NotesFile = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# "E" with an acute accent built from its code point so this script stays pure
# ASCII (PowerShell 5.1 without a BOM).
$appDisplayName = "R" + [char]0x00C9 + "SIVO"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)


function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}


function Get-AppVersion {
    param([string]$VersionFilePath)

    if (-not (Test-Path -LiteralPath $VersionFilePath -PathType Leaf)) {
        throw "Version file not found: $VersionFilePath"
    }
    $text = [System.IO.File]::ReadAllText($VersionFilePath)
    $match = [regex]::Match($text, '__version__\s*=\s*"(\d+\.\d+\.\d+)"')
    if (-not $match.Success) {
        throw ('No __version__ = "MAJOR.MINOR.PATCH" found in {0}' -f $VersionFilePath)
    }
    return $match.Groups[1].Value
}


function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ('{0} failed with exit code {1}' -f $FilePath, $LASTEXITCODE)
    }
}


function Find-Iscc {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"))
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    throw "ISCC.exe (Inno Setup 6) was not found. Install it with: winget install --id JRSoftware.InnoSetup -e"
}


$versionFilePath = Join-Path $repoRoot "desktop\version.py"
$specPath = Join-Path $repoRoot "desktop\resivo.spec"
$issPath = Join-Path $repoRoot "desktop\installer\resivo.iss"
$pythonExe = Join-Path $repoRoot "desktop\.venv\Scripts\python.exe"
$buildDir = Join-Path $repoRoot "build\resivo"
$distAppDir = Join-Path $repoRoot "dist\RESIVO"
$distInstallerDir = Join-Path $repoRoot "dist\installer"

$version = Get-AppVersion -VersionFilePath $versionFilePath
$tag = "v$version"
$installerName = "Setup-RESIVO-$version.exe"
$installerPath = Join-Path $distInstallerDir $installerName
$checksumPath = Join-Path $distInstallerDir "SHA256SUMS.txt"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

Write-Host "$appDisplayName release builder"
Write-Host "Version: $version (from desktop\version.py)"

Push-Location -LiteralPath $repoRoot
try {
    if ($SkipBuild) {
        Write-Step "Skipping PyInstaller build (-SkipBuild)"
        if (-not (Test-Path -LiteralPath (Join-Path $distAppDir "RESIVO.exe") -PathType Leaf)) {
            throw "dist\RESIVO\RESIVO.exe is missing; run again without -SkipBuild."
        }
    }
    else {
        Write-Step "Cleaning build\resivo, dist\RESIVO and dist\installer"
        foreach ($path in @($buildDir, $distAppDir, $distInstallerDir)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }

        if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
            throw "Python virtual environment not found: $pythonExe"
        }

        Write-Step "Building the PyInstaller bundle (desktop\resivo.spec)"
        Invoke-Native -FilePath $pythonExe -Arguments @(
            "-m", "PyInstaller", "--noconfirm", "--clean", $specPath
        )
    }

    Write-Step "Compiling the installer (desktop\installer\resivo.iss)"
    $iscc = Find-Iscc
    Invoke-Native -FilePath $iscc -Arguments @(
        ("/DMyAppVersion=" + $version), $issPath
    )

    if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
        throw "Installer was not produced: $installerPath"
    }

    Write-Step "Writing SHA256SUMS.txt"
    $hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToUpperInvariant()
    # Format: <UPPERCASE_SHA256><two spaces><file name> (sha256sum compatible).
    $checksumLine = "$hash  Setup-RESIVO-$version.exe"
    [System.IO.File]::WriteAllText($checksumPath, $checksumLine + "`r`n", $utf8NoBom)

    Write-Step "Resolving release notes"
    $defaultNotes = Join-Path $repoRoot ("docs\release-notes\" + $version + ".md")
    if ([string]::IsNullOrWhiteSpace($NotesFile)) {
        if (Test-Path -LiteralPath $defaultNotes -PathType Leaf) {
            $NotesFile = $defaultNotes
        }
        else {
            $NotesFile = Join-Path ([System.IO.Path]::GetTempPath()) ("resivo-release-notes-" + $tag + ".md")
            $template = @"
$appDisplayName $tag

Describe the user-facing changes in this release before publishing.

- 
"@
            [System.IO.File]::WriteAllText($NotesFile, $template + "`r`n", $utf8NoBom)
            Write-Host "No docs\release-notes\$version.md found; generated a template:"
            Write-Host "  $NotesFile"
        }
    }
    elseif (-not (Test-Path -LiteralPath $NotesFile -PathType Leaf)) {
        throw "Release notes file not found: $NotesFile"
    }

    Write-Host ""
    Write-Host "=== $appDisplayName $tag built - NOTHING WAS PUBLISHED ===" -ForegroundColor Green
    Write-Host "Installer : $installerPath"
    Write-Host "Checksums : $checksumPath"
    Write-Host "SHA-256   : $hash"
    Write-Host "Notes     : $NotesFile"
    Write-Host ""
    Write-Host "Publish with GitHub CLI (run it yourself):"
    Write-Host ""
    Write-Host "gh release create $tag `"$installerPath`" `"$checksumPath`" --title `"$appDisplayName $tag`" --notes-file `"$NotesFile`""
    Write-Host ""
    Write-Host "Or publish from the GitHub website:"
    Write-Host "  1. Open https://github.com/anesdevv/residence-management-system/releases/new"
    Write-Host "  2. Tag: $tag (target: main) - Title: $appDisplayName $tag"
    Write-Host "  3. Upload exactly two assets: $installerName and SHA256SUMS.txt"
    Write-Host "  4. Tick 'Set as the latest release' for a stable release, or"
    Write-Host "     'Set as a pre-release' for a test build the app will ignore."
    Write-Host "  5. Publish. The running app checks /releases/latest every 24 hours."
    Write-Host ""
}
finally {
    Pop-Location
}
