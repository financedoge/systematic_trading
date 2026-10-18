param([switch]$PlanOnly)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$EvidenceRoot = Join-Path $RepoRoot 'var/maintenance/windows-cutover'
function Read-Evidence([string]$Name) {
    Get-Content -LiteralPath (Join-Path $EvidenceRoot $Name) -Raw | ConvertFrom-Json
}
function Docker-Json([string[]]$Arguments) {
    $Output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker inspection failed: $($Arguments[0])" }
    $Output | ConvertFrom-Json
}
$Restore = Read-Evidence 'native-restore-acceptance.json'
$ColdStart = Read-Evidence 'native-cold-start-acceptance.json'
$Backup = Read-Evidence 'native-backup-identity-recovery.json'
$Calculation = Read-Evidence 'native-production-calculation.json'
$Current = Get-Content -LiteralPath (Join-Path $RepoRoot 'var/run/strategy-compute.json') -Raw | ConvertFrom-Json
$Profile = Get-Content -LiteralPath (Join-Path $RepoRoot 'config/service-manifest.json') -Raw | ConvertFrom-Json
if (-not $Restore.passed -or -not $ColdStart.passed -or -not $ColdStart.docker_daemon_unavailable -or
    -not $Backup.exact_native_manifest_readback -or $Backup.snapshot -notmatch '^[a-f0-9]{64}$' -or
    $Calculation.phase -ne 'complete' -or $Current.phase -ne 'complete' -or
    $Current.revision -ne $Calculation.revision -or $Calculation.resources.runtime -ne 'windows-native' -or
    $Profile.profile -ne 'native-windows') { throw 'Native migration acceptance is incomplete.' }
$ContainerName = 'systematic-trading-clickhouse'
$Containers = @(Docker-Json @('container','inspect',$ContainerName))
if ($Containers.Count -ne 1) { throw 'Expected one project ClickHouse container.' }
$Container = $Containers[0]
$ExpectedCompose = Join-Path $RepoRoot 'deploy/clickhouse/docker-compose.yml'
if ($Container.State.Running -or $Container.Id -notlike 'c0d7a6e7b293*' -or
    [IO.Path]::GetFullPath($Container.Config.Labels.'com.docker.compose.project.config_files') -ne $ExpectedCompose) {
    throw 'ClickHouse container is running or ownership changed.'
}
$VolumeNames = @('clickhouse_clickhouse_data','nats_nats_jetstream_data')
$Volumes = @(Docker-Json (@('volume','inspect') + $VolumeNames))
foreach ($Volume in $Volumes) {
    $ExpectedProject = if ($Volume.Name -eq 'clickhouse_clickhouse_data') { 'clickhouse' } else { 'nats' }
    if ($Volume.Labels.'com.docker.compose.project' -ne $ExpectedProject -or $Volume.Driver -ne 'local') {
        throw 'Legacy volume ownership changed.'
    }
    $Users = @(& docker ps -a --filter "volume=$($Volume.Name)" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0 -or @($Users | Where-Object { $_ -ne $Container.Id.Substring(0,12) }).Count) {
        throw 'A legacy volume has another container reference.'
    }
}
$ImageIds = @(
    'sha256:27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59',
    'sha256:cd3fcd4ecdda44e3a66728a5334af0a959bc3979b32810e033d1c547241cd0f4',
    'sha256:a73b5c0fb6f88e02357aead0906ad53882b07e4d202327489798844ba745e64d'
)
$Images = @(Docker-Json (@('image','inspect') + $ImageIds))
if (@($Images | Where-Object { $_.Id -notin $ImageIds }).Count -or $Images.Count -ne 3) {
    throw 'Legacy image identity changed.'
}
$ReceiptPath = Join-Path $EvidenceRoot 'docker-retirement.json'
$Receipt = [ordered]@{
    at=(Get-Date).ToUniversalTime().ToString('o'); completed=$false
    native_restore_verified=$true; native_cold_start_verified=$true
    native_backup_snapshot=$Backup.snapshot; native_calculation_revision=$Calculation.revision
    docker_data_disk='D:\systematic_trading_data\docker\DockerDesktopWSL\disk\docker_data.vhdx'
    container=@{name=$ContainerName;id=$Container.Id}; volumes=$VolumeNames; images=$ImageIds
    removed=@(); reason='Verified native Windows migration; project-owned legacy runtime retirement'
}
if ($PlanOnly) { $Receipt | ConvertTo-Json -Depth 5; return }
$Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
foreach ($Action in @(
    @{kind='container';ids=@($Container.Id)},
    @{kind='volume';ids=$VolumeNames},
    @{kind='image';ids=$ImageIds}
)) {
    foreach ($Identity in $Action.ids) {
        & docker $Action.kind rm $Identity
        if ($LASTEXITCODE -ne 0) { throw "Targeted $($Action.kind) retirement failed; inspect saved partial receipt." }
        $Receipt.removed += @{kind=$Action.kind;id=$Identity}
        $Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
    }
}
$RemainingVolumes = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0 -or @($RemainingVolumes | Where-Object { $_ -in $VolumeNames }).Count) {
    throw 'Legacy volumes remain or cannot be checked.'
}
$RemainingImages = @(& docker image ls -a --no-trunc --format '{{.ID}}')
if ($LASTEXITCODE -ne 0 -or @($RemainingImages | Where-Object { $_ -in $ImageIds }).Count) {
    throw 'Legacy images remain or cannot be checked.'
}
$Receipt.completed=$true
$Receipt.completed_at=(Get-Date).ToUniversalTime().ToString('o')
$Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
$Receipt | ConvertTo-Json -Depth 5
