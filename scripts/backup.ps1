param(
  [string]$BackupRoot = ".\\backups"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Compose = @("-f", "docker-compose.production.yml")
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path (Resolve-Path -Path (New-Item -ItemType Directory -Force -Path $BackupRoot).FullName) "surface-analyzer-$stamp"
New-Item -ItemType Directory -Force -Path $target | Out-Null

docker compose @Compose ps --status running --services | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Cannot reach the Compose installation." }

try {
  docker compose @Compose stop api
  if ($LASTEXITCODE -ne 0) { throw "Could not stop API before backup." }

  docker compose @Compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' | Set-Content -Encoding Byte -Path (Join-Path $target "database.dump")
  if ($LASTEXITCODE -ne 0) { throw "Database backup failed." }

  docker compose @Compose cp api:/data/uploads (Join-Path $target "uploads")
  if ($LASTEXITCODE -ne 0) { throw "Uploads backup failed." }

  Copy-Item ".env" (Join-Path $target ".env")
  Write-Host "Backup created: $target"
} finally {
  docker compose @Compose start api | Out-Null
}
