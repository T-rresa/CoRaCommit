# Start CoRaCommit from the prebuilt GHCR images (no local build).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required. Install Docker Desktop / Docker Engine first."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.deploy.example" ".env"
    Write-Host "Created .env from .env.deploy.example. Edit it if needed."
}

if (docker compose version 2>$null) {
    $ComposeCmd = "docker"
    $ComposeArgs = @("compose")
} else {
    $ComposeCmd = "docker-compose"
    $ComposeArgs = @()
}

$ComposeFile = "docker-compose.release.yml"

function Get-HealthUrl([string]$Service, [int]$Port) {
    $mapping = & $ComposeCmd @ComposeArgs -f $ComposeFile port $Service $Port 2>$null | Select-Object -First 1
    $hostPort = $Port
    if ($mapping -and $mapping.Contains(":")) {
        $parts = $mapping.Split(":")
        $hostPort = $parts[$parts.Length - 1]
    }
    return "http://127.0.0.1:$hostPort/api/health"
}

Write-Host "Pulling prebuilt CoRaCommit images from GHCR..."
$PullOk = $false
try {
    & $ComposeCmd @ComposeArgs -f $ComposeFile pull
    $PullOk = ($LASTEXITCODE -eq 0)
} catch {
    $PullOk = $false
}
if (-not $PullOk) {
    Write-Host ""
    Write-Host "Pull failed. If the packages are private, log in first:"
    Write-Host "  `$env:GHCR_TOKEN | docker login ghcr.io -u <github-user> --password-stdin"
    throw "Could not pull the prebuilt images."
}

Write-Host "Starting CoRaCommit services..."
& $ComposeCmd @ComposeArgs -f $ComposeFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start the stack. Check the output above."
}

Write-Host "Waiting for health endpoints..."
$urls = @(
    (Get-HealthUrl "retrieval-backend" 8000),
    (Get-HealthUrl "evaluation-backend" 8001),
    (Get-HealthUrl "node-api" 3001)
)
for ($i = 0; $i -lt 60; $i++) {
    $ok = 0
    foreach ($url in $urls) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 | Out-Null
            $ok++
        } catch { }
    }
    if ($ok -eq 3) {
        Write-Host "All services are healthy."
        Write-Host "Next: install the VSIX, open the CoRaCommit sidebar, set an API key, and generate."
        exit 0
    }
    Start-Sleep -Seconds 5
}

throw "Services did not become healthy in time. Check logs with: $ComposeCmd $($ComposeArgs -join ' ') -f $ComposeFile logs"