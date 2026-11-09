param(
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker was not found. Install Docker Desktop or Docker Engine with the Compose plugin, then rerun this installer."
}

docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Docker Compose is unavailable. Install the Docker Compose plugin and retry."
}

if (-not (Test-Path ".env")) {
  $passwordBytes = New-Object byte[] 32
  $secretBytes = New-Object byte[] 48
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($passwordBytes)
    $rng.GetBytes($secretBytes)
  } finally {
    $rng.Dispose()
  }
  $password = [Convert]::ToBase64String($passwordBytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  $secret = [Convert]::ToBase64String($secretBytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  $envText = Get-Content ".env.production.example" -Raw
  $envText = $envText.Replace("replace-this-password", $password)
  $envText = $envText.Replace("replace-with-a-random-secret-at-least-32-characters", $secret)
  [System.IO.File]::WriteAllText((Join-Path $Root ".env"), $envText, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Created .env with unique database and signing secrets."
} else {
  Write-Host "Using existing .env; installer will not overwrite your configuration."
}

if (-not $SkipBuild) {
  docker compose -f docker-compose.production.yml up -d --build
} else {
  docker compose -f docker-compose.production.yml up -d
}

if ($LASTEXITCODE -ne 0) {
  throw "Docker Compose failed. Inspect logs with: docker compose -f docker-compose.production.yml logs"
}
Write-Host "Surface Analyzer services have been started."
Write-Host "Studio: http://localhost:3000"
Write-Host "API:    http://localhost:8000"
Write-Host "Review .env and configure a TLS reverse proxy before exposing this installation to the internet."
