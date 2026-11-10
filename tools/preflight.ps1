<#
.SYNOPSIS
    Pre-flight check for running the RÉSIVO Desktop Console on any clean Windows 10/11 64-bit PC.
.DESCRIPTION
    Pure Windows PowerShell 5.1 script requiring no external modules and no administrator rights.
    Inspects OS version/bitness, free disk space, Supabase DNS/HTTPS reachability, system clock,
    display DPI scaling, writable install/data folders, and Zone.Identifier download blocks.
    Never reads or prints passwords or API keys.
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\preflight.ps1
#>
[CmdletBinding()]
param(
    [string]$SupabaseHost = "",
    [string]$PackagePath = ""
)

$ErrorActionPreference = "Continue"
$script:FailCount = 0
$script:WarnCount = 0

function Write-Check {
    param(
        [ValidateSet("PASS", "WARN", "FAIL", "INFO")]
        [string]$Status,
        [string]$Label,
        [string]$Detail
    )
    $color = switch ($Status) {
        "PASS" { "Green" }
        "WARN" { "Yellow" }
        "FAIL" { "Red" }
        default { "Cyan" }
    }
    Write-Host ("[{0}] {1}: {2}" -f $Status, $Label, $Detail) -ForegroundColor $color
    if ($Status -eq "FAIL") { $script:FailCount++ }
    elseif ($Status -eq "WARN") { $script:WarnCount++ }
}

Write-Host "=== RÉSIVO Windows Pre-Flight Check ===" -ForegroundColor Cyan

# 1. Discover Supabase hostname safely (no secret values printed)
if ([string]::IsNullOrWhiteSpace($SupabaseHost)) {
    $envCandidates = @(
        (Join-Path $PSScriptRoot "..\.env"),
        (Join-Path $PSScriptRoot "..\desktop\.env"),
        (Join-Path $PSScriptRoot "..\dist\RESIVO\.env"),
        (Join-Path $env:LOCALAPPDATA "Programs\RESIVO\.env")
    )
    foreach ($candidate in $envCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            try {
                $line = Get-Content -LiteralPath $candidate -Encoding UTF8 | Where-Object { $_ -match '^\s*SUPABASE_URL\s*=' } | Select-Object -First 1
                if ($line) {
                    $rawUrl = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
                    $uri = [System.Uri]$rawUrl
                    if ($uri.Host) {
                        $SupabaseHost = $uri.Host
                        break
                    }
                }
            } catch {}
        }
    }
}
if ([string]::IsNullOrWhiteSpace($SupabaseHost)) {
    $SupabaseHost = "kjqbnurycfjsuufibkac.supabase.co"
}

# 2. Windows version & build (require Windows 10 21H2 / build 19044+ or Windows 11)
try {
    $cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction Stop
    $buildNum = [int]$cv.CurrentBuildNumber
    $displayVer = $cv.DisplayVersion
    if (-not $displayVer) { $displayVer = $cv.ReleaseId }
    $osCaption = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    $okWin = $buildNum -ge 19044
    $status = if ($okWin) { "PASS" } else { "FAIL" }
    Write-Check -Status $status -Label "Windows OS" -Detail "$osCaption (Version $displayVer, Build $buildNum)"
} catch {
    Write-Check -Status "WARN" -Label "Windows OS" -Detail ([System.Environment]::OSVersion.VersionString)
}

# 3. 64-bit OS check
$is64Os = [System.Environment]::Is64BitOperatingSystem
Write-Check -Status $(if ($is64Os) { "PASS" } else { "FAIL" }) -Label "Architecture" -Detail $(if ($is64Os) { "64-bit Windows (x64)" } else { "32-bit Windows (unsupported)" })

# 4. Free disk space on target drive (%LOCALAPPDATA%)
try {
    $targetRoot = Split-Path -Qualifier $env:LOCALAPPDATA
    $driveLetter = $targetRoot.TrimEnd(':')
    $psDrive = Get-PSDrive -Name $driveLetter -ErrorAction Stop
    $freeMB = [math]::Round($psDrive.Free / 1MB, 0)
    $okSpace = $freeMB -ge 500
    Write-Check -Status $(if ($okSpace) { "PASS" } else { "FAIL" }) -Label "Disk Space ($targetRoot)" -Detail "$freeMB MB free (minimum ~500 MB recommended)"
} catch {
    Write-Check -Status "WARN" -Label "Disk Space" -Detail "Could not query drive space: $($_.Exception.Message)"
}

# 5. Install & per-user writable paths check
$pathsToCheck = @(
    @{ Name = "Install Dir"; Path = (Join-Path $env:LOCALAPPDATA "Programs\RESIVO") },
    @{ Name = "AppData (Logs)"; Path = (Join-Path $env:APPDATA "RESIVO") },
    @{ Name = "LocalAppData (Session)"; Path = (Join-Path $env:LOCALAPPDATA "RESIVO") }
)
foreach ($entry in $pathsToCheck) {
    $dir = $entry.Path
    $probeBase = $dir
    while (-not (Test-Path -LiteralPath $probeBase) -and (Split-Path -Parent $probeBase)) {
        $probeBase = Split-Path -Parent $probeBase
    }
    $probeFile = Join-Path $probeBase ("resivo_preflight_" + [System.Guid]::NewGuid().ToString("N") + ".tmp")
    try {
        [System.IO.File]::WriteAllText($probeFile, "ok")
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
        Write-Check -Status "PASS" -Label $entry.Name -Detail "Writable ($dir)"
    } catch {
        Write-Check -Status "FAIL" -Label $entry.Name -Detail "Not writable ($dir): $($_.Exception.Message)"
    }
}

# 6. System date, time & timezone
$nowLocal = Get-Date
$nowUtc = $nowLocal.ToUniversalTime()
$tz = [System.TimeZoneInfo]::Local
Write-Check -Status "INFO" -Label "System Clock" -Detail ("Local={0:yyyy-MM-dd HH:mm:ss} | UTC={1:yyyy-MM-dd HH:mm:ss} | TZ={2}" -f $nowLocal, $nowUtc, $tz.Id)

# 7. DNS + HTTPS reachability & clock skew check
$dnsOk = $false
try {
    $addrs = [System.Net.Dns]::GetHostAddresses($SupabaseHost)
    $dnsOk = $addrs.Count -gt 0
    Write-Check -Status "PASS" -Label "DNS ($SupabaseHost)" -Detail "Resolved $($addrs.Count) address(es)"
} catch {
    Write-Check -Status "FAIL" -Label "DNS ($SupabaseHost)" -Detail "Resolution failed: $($_.Exception.Message)"
}

if ($dnsOk) {
    $probeUrl = "https://$SupabaseHost/rest/v1/"
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        $req = [System.Net.HttpWebRequest]::Create($probeUrl)
        $req.Method = "HEAD"
        $req.Timeout = 6000
        $req.AllowAutoRedirect = $false
        $resp = $null
        try {
            $resp = $req.GetResponse()
        } catch [System.Net.WebException] {
            $resp = $_.Exception.Response
            if ($null -eq $resp) { throw }
        }
        $httpResp = [System.Net.HttpWebResponse]$resp
        $statusCode = [int]$httpResp.StatusCode
        $dateHdr = $httpResp.Headers["Date"]
        $httpResp.Close()
        Write-Check -Status "PASS" -Label "HTTPS ($SupabaseHost)" -Detail "Reachable over TLS (HTTP $statusCode)"

        if ($dateHdr) {
            try {
                $serverUtc = [System.DateTimeOffset]::Parse($dateHdr).UtcDateTime
                $drift = [math]::Abs(($nowUtc - $serverUtc).TotalSeconds)
                $clockStatus = if ($drift -le 300) { "PASS" } else { "WARN" }
                Write-Check -Status $clockStatus -Label "Clock Drift" -Detail ("$([math]::Round($drift, 0)) seconds vs server UTC (recommended <= 300s)")
            } catch {}
        }
    } catch {
        Write-Check -Status "FAIL" -Label "HTTPS ($SupabaseHost)" -Detail "TLS/Network error: $($_.Exception.Message)"
    }
}

# 8. Display scaling & resolution
try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $regDpi = (Get-ItemProperty "HKCU:\Control Panel\Desktop\WindowMetrics" -Name AppliedDPI -ErrorAction SilentlyContinue).AppliedDPI
    $scalePct = if ($regDpi) { [math]::Round(([int]$regDpi / 96.0) * 100) } else { 100 }
    Write-Check -Status "PASS" -Label "Display" -Detail "$($bounds.Width)x$($bounds.Height) (WorkingArea=$($workArea.Width)x$($workArea.Height)), Scale=${scalePct}%"
} catch {
    Write-Check -Status "INFO" -Label "Display" -Detail "Scale query skipped ($($_.Exception.Message))"
}

# 9. Zone.Identifier (Mark of the Web) check on downloaded files
$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($PackagePath)) {
    if (Test-Path -LiteralPath $PackagePath) { $candidates += Get-Item -LiteralPath $PackagePath }
} else {
    $searchDirs = @(
        $PWD.Path,
        (Split-Path -Parent $PSScriptRoot),
        (Join-Path (Split-Path -Parent $PSScriptRoot) "dist"),
        (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\installer"),
        (Join-Path $env:LOCALAPPDATA "Programs\RESIVO"),
        (Join-Path $env:USERPROFILE "Downloads")
    ) | Select-Object -Unique
    foreach ($d in $searchDirs) {
        if (Test-Path -LiteralPath $d) {
            $candidates += Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue | Where-Object {
                $_.Name -match '^(Setup-RESIVO-.*\.exe|RESIVO-.*\.zip|RESIVO\.exe)$'
            }
        }
    }
}

if ($candidates.Count -eq 0) {
    Write-Check -Status "INFO" -Label "Zone.Identifier" -Detail "No Setup-RESIVO-*.exe / RESIVO-*.zip / RESIVO.exe found in checked folders (pass -PackagePath to inspect a file)."
} else {
    foreach ($file in ($candidates | Sort-Object FullName -Unique)) {
        $zone = Get-Item -LiteralPath $file.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue
        if ($zone) {
            Write-Check -Status "WARN" -Label "Zone.Identifier" -Detail "$($file.Name) is marked as downloaded/blocked. Right-click -> Properties -> Unblock (or run: Unblock-File '$($file.FullName)')."
        } else {
            Write-Check -Status "PASS" -Label "Zone.Identifier" -Detail "$($file.Name) is unblocked."
        }
    }
}

Write-Host ""
Write-Host ("Pre-flight complete: {0} failure(s), {1} warning(s)." -f $script:FailCount, $script:WarnCount) -ForegroundColor $(if ($script:FailCount -eq 0) { "Green" } else { "Red" })
if ($script:FailCount -gt 0) { exit 1 }
exit 0
