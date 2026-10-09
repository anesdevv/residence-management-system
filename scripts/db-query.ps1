param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
. .\scripts\load-env.ps1
$py = "C:\Users\Admin\AppData\Local\Temp\opencode\pgvenv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { Write-Error "pgvenv python not found: $py"; exit 2 }
& $py .\scripts\dbquery.py @Rest
exit $LASTEXITCODE