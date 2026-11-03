$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL is required"
}
if (-not $env:BACKUP_DIRECTORY) {
    throw "BACKUP_DIRECTORY is required"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $env:BACKUP_DIRECTORY | Out-Null
$backupFile = Join-Path $env:BACKUP_DIRECTORY "wrw-$timestamp.dump"

pg_dump --dbname="$env:DATABASE_URL" --format=custom --file="$backupFile"
Write-Output "Database backup created: $backupFile"
