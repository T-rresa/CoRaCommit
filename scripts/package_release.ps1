$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$Root/scripts/package_extension.ps1"

$Bundle = Join-Path $Root "release/coracommit-2.1.0-bundle.zip"
if (Test-Path $Bundle) { Remove-Item $Bundle -Force }

$Items = @(
    "release/coracommit-2.1.0.vsix",
    "docker-compose.deploy.yml",
    "docker-compose.release.yml",
    ".env.deploy.example",
    "README.md",
    "DEPLOY.md",
    "LICENSE",
    "docs",
    "scripts",
    "resource_demo"
) | ForEach-Object { Join-Path $Root $_ }

Compress-Archive -Path $Items -DestinationPath $Bundle -Force

$Vsix = Join-Path $Root "release/coracommit-2.1.0.vsix"
Get-FileHash $Vsix -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower()) *$Vsix" } |
    Set-Content (Join-Path $Root "release/checksums.txt")
Get-FileHash $Bundle -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower()) *$Bundle" } |
    Add-Content (Join-Path $Root "release/checksums.txt")

Write-Host "Release bundle: $Bundle"
Get-Content (Join-Path $Root "release/checksums.txt")