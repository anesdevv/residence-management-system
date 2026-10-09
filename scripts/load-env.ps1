param([string]$EnvFile = "supabase\.env")
if (-not (Test-Path -LiteralPath $EnvFile)) { Write-Error "Env file not found: $EnvFile"; exit 1 }
Get-Content -LiteralPath $EnvFile | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$') {
    [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
  }
}
Write-Host "Loaded $EnvFile into process env"