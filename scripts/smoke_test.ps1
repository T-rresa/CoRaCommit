$ErrorActionPreference = "Stop"

function Get-EnvPort([string]$Name, [string]$Default) {
    if (Test-Path ".env") {
        $line = Get-Content ".env" | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
        if ($line) { return ($line -split "=", 2)[1].Trim() }
    }
    return $Default
}

$RetrievalPort = Get-EnvPort "RETRIEVAL_PORT" "8000"
$EvaluationPort = Get-EnvPort "EVALUATION_PORT" "8001"
$NodeApiPort = Get-EnvPort "NODE_API_PORT" "3001"

function Check-Health($Name, $Url) {
    Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10 | Out-Null
    Write-Host "OK   $Name  $Url"
}

Check-Health "retrieval backend" "http://127.0.0.1:$RetrievalPort/api/health"
Check-Health "evaluation backend" "http://127.0.0.1:$EvaluationPort/api/health"
Check-Health "node api" "http://127.0.0.1:$NodeApiPort/api/health"

$body = @{ diff = "diff --git a/a.txt b/a.txt`n+hello" } | ConvertTo-Json -Compress
$response = Invoke-RestMethod -Uri "http://127.0.0.1:$NodeApiPort/api/similarity-search" `
    -Method Post -ContentType "application/json" -Body $body

if ($null -eq $response.matches) {
    throw "Similarity search did not return a matches field."
}
Write-Host "OK   similarity search returned $($response.matches.Count) matches"
Write-Host "Smoke test passed."