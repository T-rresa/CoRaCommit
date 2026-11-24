$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "vscode_extension")

npm ci
npm run compile
npm run package

$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Release | Out-Null
$Vsix = Get-ChildItem -Path . -Filter "*.vsix" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Copy-Item $Vsix.FullName $Release
Write-Host "Packaged: $(Join-Path $Release $Vsix.Name)"