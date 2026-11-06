# PostgreSQL Windows service control with an explicit administrator request.
#
# The runtime keeps PostgreSQL as an external Windows service (default
# postgresql-x64-18). A non-elevated operator shell cannot start or restart that
# service; this helper performs the action directly when the shell is already
# elevated and otherwise asks Windows for administrator permission once through
# the standard UAC prompt. File contents, data and owners are never touched.
#
# Dot-source this file for the functions, or run it with -Action for a JSON
# result (used by the elevated child process and by manual diagnosis).

param(
    [ValidateSet("Ensure", "Start", "Restart", "Status")]
    [string]$Action = "Status",
    [string]$ServiceName = "",
    [int]$WaitSeconds = 90
)

$ErrorActionPreference = "Stop"

# Captured at load time: when this file is dot-sourced, $PSCommandPath can refer
# to the caller's script, but the elevated child must import this exact file.
$script:PostgresServiceLibraryPath = $MyInvocation.MyCommand.Path
$script:DefaultPostgresServiceName = "postgresql-x64-18"

function Get-PostgresServiceName {
    param([string]$ServiceName)

    if ($ServiceName) { return $ServiceName }
    if ($env:ST_POSTGRES_SERVICE_NAME) { return [string]$env:ST_POSTGRES_SERVICE_NAME }
    return $script:DefaultPostgresServiceName
}

function Test-IsElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PostgresService {
    param([string]$ServiceName)

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    return [pscustomobject]@{
        Found = ($null -ne $service)
        Name = $name
        Status = if ($service) { [string]$service.Status } else { "Missing" }
    }
}

function Wait-PostgresServiceRunning {
    param(
        [string]$ServiceName,
        [int]$WaitSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $service) { return $false }
        if ($service.Status -eq "Running") { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return ((Get-Service -Name $ServiceName -ErrorAction SilentlyContinue).Status -eq "Running")
}

function Invoke-PostgresServiceControlDirect {
    param(
        [ValidateSet("Start", "Restart")]
        [string]$Action,
        [string]$ServiceName,
        [int]$WaitSeconds = 90
    )

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $service) {
        return [pscustomobject]@{
            Ok = $false; Action = $Action; ServiceName = $name; Method = "direct"
            Error = "PostgreSQL Windows service '$name' was not found."
        }
    }

    try {
        if ($Action -eq "Start") {
            if ($service.Status -ne "Running") {
                Start-Service -Name $name -ErrorAction Stop
            }
        } elseif ($service.Status -eq "Running") {
            Restart-Service -Name $name -Force -ErrorAction Stop
        } else {
            # Restart on a stopped service must not leave the database down.
            Start-Service -Name $name -ErrorAction Stop
        }
    } catch {
        $status = (Get-Service -Name $name -ErrorAction SilentlyContinue).Status
        return [pscustomobject]@{
            Ok = $false; Action = $Action; ServiceName = $name; Method = "direct"
            Error = "Windows service control failed ($($_.Exception.Message)). Current status: $status."
        }
    }

    if (-not (Wait-PostgresServiceRunning -ServiceName $name -WaitSeconds $WaitSeconds)) {
        $status = (Get-Service -Name $name -ErrorAction SilentlyContinue).Status
        return [pscustomobject]@{
            Ok = $false; Action = $Action; ServiceName = $name; Method = "direct"
            Error = "Service '$name' did not reach Running within $WaitSeconds seconds. Current status: $status."
        }
    }

    return [pscustomobject]@{
        Ok = $true; Action = $Action; ServiceName = $name; Method = "direct"; Error = $null
    }
}

function Get-PowerShellHostPath {
    $candidate = if ($PSVersionTable.PSEdition -eq "Core") {
        Join-Path $PSHOME "pwsh.exe"
    } else {
        Join-Path $PSHOME "powershell.exe"
    }
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    try {
        $current = (Get-Process -Id $PID -ErrorAction Stop).Path
        if ($current) { return $current }
    } catch {
        # Fall back to PATH resolution when the host path is unreadable.
    }
    return "powershell.exe"
}

function ConvertTo-SingleQuotedLiteral {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function New-ElevatedPostgresChildScript {
    param(
        [ValidateSet("Start", "Restart")]
        [string]$Action,
        [string]$ServiceName,
        [string]$LibraryPath,
        [string]$ResultPath,
        [int]$WaitSeconds = 90
    )

    return @"
`$ErrorActionPreference = 'Stop'
`$resultPath = $(ConvertTo-SingleQuotedLiteral $ResultPath)
try {
    . $(ConvertTo-SingleQuotedLiteral $LibraryPath)
    `$result = Invoke-PostgresServiceControlDirect -Action $(ConvertTo-SingleQuotedLiteral $Action) -ServiceName $(ConvertTo-SingleQuotedLiteral $ServiceName) -WaitSeconds $WaitSeconds
    `$result | ConvertTo-Json -Compress -Depth 6 | Set-Content -LiteralPath `$resultPath -Encoding utf8
    if (`$result.Ok) { exit 0 } else { exit 1 }
} catch {
    @{ Ok = `$false; Action = $(ConvertTo-SingleQuotedLiteral $Action); ServiceName = $(ConvertTo-SingleQuotedLiteral $ServiceName); Method = 'elevated'; Error = [string]`$_ } |
        ConvertTo-Json -Compress -Depth 6 | Set-Content -LiteralPath `$resultPath -Encoding utf8
    exit 1
}
"@
}

function Invoke-ElevatedPostgresAction {
    param(
        [ValidateSet("Start", "Restart")]
        [string]$Action,
        [string]$ServiceName,
        [int]$WaitSeconds = 90
    )

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $libraryPath = $script:PostgresServiceLibraryPath
    if (-not $libraryPath) { $libraryPath = $PSCommandPath }

    $tempRoot = [System.IO.Path]::GetTempPath()
    $token = [guid]::NewGuid().ToString("N")
    $childScriptPath = Join-Path $tempRoot "postgres-service-$token.ps1"
    $resultPath = Join-Path $tempRoot "postgres-service-$token.json"

    $childScript = New-ElevatedPostgresChildScript `
        -Action $Action `
        -ServiceName $name `
        -LibraryPath $libraryPath `
        -ResultPath $resultPath `
        -WaitSeconds $WaitSeconds

    try {
        Set-Content -LiteralPath $childScriptPath -Value $childScript -Encoding utf8
        $shellPath = Get-PowerShellHostPath
        # Quote the script path for Windows PowerShell 5.1, which joins the
        # ArgumentList without adding quotes (temp paths can contain spaces).
        $quotedChildScriptPath = '"' + $childScriptPath + '"'
        try {
            $elevated = Start-Process `
                -FilePath $shellPath `
                -ArgumentList @(
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    $quotedChildScriptPath
                ) `
                -Verb RunAs `
                -Wait `
                -PassThru `
                -WindowStyle Hidden
        } catch {
            $cancelled = $false
            $inner = $_.Exception
            while ($inner) {
                if ($inner -is [System.ComponentModel.Win32Exception] -and $inner.NativeErrorCode -eq 1223) {
                    $cancelled = $true
                    break
                }
                $inner = $inner.InnerException
            }
            $message = if ($cancelled) {
                "Administrator permission was declined in the Windows prompt. The PostgreSQL service was not changed."
            } else {
                "Could not start the elevated Windows PowerShell helper: $($_.Exception.Message)"
            }
            return [pscustomobject]@{
                Ok = $false; Cancelled = $cancelled; Action = $Action; ServiceName = $name; Method = "elevated"; Error = $message
            }
        }

        $result = $null
        if (Test-Path -LiteralPath $resultPath) {
            try {
                $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
            } catch {
                $result = $null
            }
        }
        if ($result) {
            $result | Add-Member -NotePropertyName Method -NotePropertyValue "elevated" -Force
            $result | Add-Member -NotePropertyName Cancelled -NotePropertyValue $false -Force
            return $result
        }
        return [pscustomobject]@{
            Ok = $false; Cancelled = $false; Action = $Action; ServiceName = $name; Method = "elevated"
            Error = "The elevated PowerShell helper exited with code $($elevated.ExitCode) without a result."
        }
    } finally {
        Remove-Item -LiteralPath $childScriptPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
    }
}

function Start-PostgresService {
    param(
        [string]$ServiceName,
        [switch]$AllowElevation
    )

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $service = Get-PostgresService -ServiceName $name
    if (-not $service.Found) {
        return [pscustomobject]@{
            Ok = $false; Action = "Start"; ServiceName = $name; Method = "none"; Elevated = $false
            Error = "PostgreSQL Windows service '$name' was not found."
        }
    }
    if ($service.Status -eq "Running") {
        return [pscustomobject]@{
            Ok = $true; Action = "Start"; ServiceName = $name; Method = "none"; Elevated = $false; Error = $null
        }
    }

    if (Test-IsElevated) {
        $result = Invoke-PostgresServiceControlDirect -Action "Start" -ServiceName $name
        $result | Add-Member -NotePropertyName Elevated -NotePropertyValue $false -Force
        return $result
    }
    if (-not $AllowElevation) {
        return [pscustomobject]@{
            Ok = $false; Action = "Start"; ServiceName = $name; Method = "none"; Elevated = $false
            Error = "Administrator permission is required to start the PostgreSQL Windows service. Rerun from an Administrator PowerShell or allow the elevation prompt."
        }
    }
    $result = Invoke-ElevatedPostgresAction -Action "Start" -ServiceName $name
    $result | Add-Member -NotePropertyName Elevated -NotePropertyValue $true -Force
    return $result
}

function Restart-PostgresService {
    param(
        [string]$ServiceName,
        [switch]$AllowElevation
    )

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $service = Get-PostgresService -ServiceName $name
    if (-not $service.Found) {
        return [pscustomobject]@{
            Ok = $false; Action = "Restart"; ServiceName = $name; Method = "none"; Elevated = $false
            Error = "PostgreSQL Windows service '$name' was not found."
        }
    }

    if (Test-IsElevated) {
        $result = Invoke-PostgresServiceControlDirect -Action "Restart" -ServiceName $name
        $result | Add-Member -NotePropertyName Elevated -NotePropertyValue $false -Force
        return $result
    }
    if (-not $AllowElevation) {
        return [pscustomobject]@{
            Ok = $false; Action = "Restart"; ServiceName = $name; Method = "none"; Elevated = $false
            Error = "Administrator permission is required to restart the PostgreSQL Windows service. Restart it from an Administrator PowerShell."
        }
    }
    $result = Invoke-ElevatedPostgresAction -Action "Restart" -ServiceName $name
    $result | Add-Member -NotePropertyName Elevated -NotePropertyValue $true -Force
    return $result
}

function Ensure-PostgresServiceStarted {
    param(
        [string]$ServiceName,
        [switch]$AllowElevation
    )

    $name = Get-PostgresServiceName -ServiceName $ServiceName
    $service = Get-PostgresService -ServiceName $name
    if (-not $service.Found) {
        return [pscustomobject]@{
            Ok = $true; Found = $false; Action = "None"; ServiceName = $name; Method = "none"; Elevated = $false
            State = "Missing"; Error = $null
        }
    }
    if ($service.Status -eq "Running") {
        return [pscustomobject]@{
            Ok = $true; Found = $true; Action = "None"; ServiceName = $name; Method = "none"; Elevated = $false
            State = "Running"; Error = $null
        }
    }

    $result = Start-PostgresService -ServiceName $name -AllowElevation:$AllowElevation
    $state = (Get-PostgresService -ServiceName $name).Status
    return [pscustomobject]@{
        Ok = $result.Ok
        Found = $true
        Action = "Start"
        ServiceName = $name
        Method = $result.Method
        Elevated = [bool]$result.Elevated
        State = $state
        Error = $result.Error
    }
}

function Invoke-PostgresServiceAction {
    param(
        [string]$Action,
        [string]$ServiceName,
        [int]$WaitSeconds = 90
    )

    switch ($Action) {
        "Status" {
            $service = Get-PostgresService -ServiceName $ServiceName
            return [pscustomobject]@{
                Ok = $service.Found; Action = "Status"; ServiceName = $service.Name; Found = $service.Found
                State = $service.Status; Elevated = (Test-IsElevated); Error = if ($service.Found) { $null } else { "Service not found." }
            }
        }
        "Start" { return Start-PostgresService -ServiceName $ServiceName -AllowElevation }
        "Restart" { return Restart-PostgresService -ServiceName $ServiceName -AllowElevation }
        "Ensure" { return Ensure-PostgresServiceStarted -ServiceName $ServiceName -AllowElevation }
        default { throw "Unknown PostgreSQL service action: $Action" }
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    $result = Invoke-PostgresServiceAction -Action $Action -ServiceName $ServiceName -WaitSeconds $WaitSeconds
    $result | ConvertTo-Json -Compress -Depth 6
    if ($result.Ok) { exit 0 }
    exit 1
}
