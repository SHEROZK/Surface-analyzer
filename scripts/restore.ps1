param(
  [Parameter(Mandatory=$true)][string]$BackupPath,
  [switch]$ConfirmDataReplacement
)
$ErrorActionPreference = "Stop"
if (-not $ConfirmDataReplacement) {
  throw "Restore replaces the current database and uploaded files. Re-run with -ConfirmDataReplacement after verifying the backup."
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$BackupPath = (Resolve-Path $BackupPath).Path
$dump = Join-Path $BackupPath "database.dump"
$uploads = Join-Path $BackupPath "uploads"
if (-not (Test-Path $dump -PathType Leaf) -or -not (Test-Path $uploads -PathType Container)) {
  throw "Backup folder must contain database.dump and uploads/."
}
$Compose = @("-f", "docker-compose.production.yml")

docker compose @Compose stop api
if ($LASTEXITCODE -ne 0) { throw "Could not stop API." }
try {
  docker compose @Compose exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < $dump
  if ($LASTEXITCODE -ne 0) { throw "Database restore failed." }
  docker compose @Compose exec -T api sh -c 'find /data/uploads -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
  if ($LASTEXITCODE -ne 0) { throw "Could not clear existing uploads." }
  docker compose @Compose cp "$uploads/." api:/data/uploads/
  if ($LASTEXITCODE -ne 0) { throw "Uploads restore failed." }
  Write-Host "Restore completed from $BackupPath"
} finally {
  docker compose @Compose start api | Out-Null
}
