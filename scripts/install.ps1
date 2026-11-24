# One-command install: start the backend stack and install the VS Code extension.
#
#   .\scripts\install.ps1           # use prebuilt GHCR images (fallback: source build)
#   .\scripts\install.ps1 -Source   # build the images from source
param([switch]$Source)

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

$Mode = if ($Source) { "source" } else { "release" }

if ($Mode -eq "release") {
    Write-Host "Pulling prebuilt CoRaCommit images from GHCR..."
    $PullOk = $false
    try {
        & $ComposeCmd @ComposeArgs -f docker-compose.release.yml pull
        $PullOk = ($LASTEXITCODE -eq 0)
    } catch {
        $PullOk = $false
    }
    if (-not $PullOk) {
        Write-Host ""
        Write-Host "Prebuilt images are not available (not published yet or no network)."
        Write-Host "Falling back to a source build."
        $Mode = "source"
    }
}

if ($Mode -eq "source") {
    $ComposeFile = "docker-compose.deploy.yml"
    Write-Host "Building and starting CoRaCommit services from source..."
    & $ComposeCmd @ComposeArgs -f $ComposeFile up -d --build
} else {
    $ComposeFile = "docker-compose.release.yml"
    Write-Host "Starting CoRaCommit services from prebuilt images..."
    & $ComposeCmd @ComposeArgs -f $ComposeFile up -d
}
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start the stack. Check the output above."
}

function Get-HealthUrl([string]$Service, [int]$Port) {
    $mapping = & $ComposeCmd @ComposeArgs -f $ComposeFile port $Service $Port 2>$null | Select-Object -First 1
    $hostPort = $Port
    if ($mapping -and $mapping.Contains(":")) {
        $parts = $mapping.Split(":")
        $hostPort = $parts[$parts.Length - 1]
    }
    return "http://127.0.0.1:$hostPort/api/health"
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
        break
    }
    Start-Sleep -Seconds 5
    if ($i -eq 59) {
        throw "Services did not become healthy in time. Check logs with: $ComposeCmd $($ComposeArgs -join ' ') -f $ComposeFile logs"
    }
}

$Vsix = Join-Path $Root "release/coracommit-2.1.0.vsix"
if (-not (Test-Path $Vsix)) {
    Write-Host "Packaging the VS Code extension..."
    & "$Root/scripts/package_extension.ps1"
}

if (Get-Command code -ErrorAction SilentlyContinue) {
    Write-Host "Installing the extension..."
    & code --install-extension $Vsix --force
    Write-Host ""
    Write-Host "Done. Reload the VS Code window (Developer: Reload Window),"
    Write-Host "open the CoRaCommit sidebar, set an API key, stage a change, and click Generate."
} else {
    Write-Host ""
    Write-Host "VS Code CLI 'code' was not found. Install the extension manually:"
    Write-Host "  $Vsix"
}