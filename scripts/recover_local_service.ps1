param(
    [ValidateSet("nats", "clickhouse", "operator", "recorder", "backup")][string]$Service,
    [string]$ProfilePath
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$recoverySettings = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
if (-not $recoverySettings.enabled.$Service) { exit 0 }
switch ($Service) {
    "nats" {
        & "$PSScriptRoot\start_nats_jetstream.ps1" -Recovery
        & $Python "$PSScriptRoot\configure_nats_stream.py" --nats-url $recoverySettings.operator.NatsUrl
        if ($LASTEXITCODE -ne 0) { throw "NATS stream recovery failed" }
    }
    "clickhouse" { & "$PSScriptRoot\start_clickhouse.ps1" -Recovery }
    "operator" {
        $options = @{}
        foreach ($property in $recoverySettings.operator.PSObject.Properties) { $options[$property.Name] = $property.Value }
        & "$PSScriptRoot\start_operator_dashboard.ps1" @options -Recovery
    }
    "recorder" {
        $options = @{}
        foreach ($property in $recoverySettings.recorder.PSObject.Properties) { $options[$property.Name] = $property.Value }
        & "$PSScriptRoot\start_market_data_recorder_service.ps1" @options -Recovery
    }
    "backup" {
        Start-Process -FilePath $Python -ArgumentList @("$PSScriptRoot\sync_databases.py", "worker") `
            -WorkingDirectory $RepoRoot -WindowStyle Hidden `
            -RedirectStandardOutput "$RepoRoot\var\log\database_sync.out.log" `
            -RedirectStandardError "$RepoRoot\var\log\database_sync.err.log" | Out-Null
    }
}
