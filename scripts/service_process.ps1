# Shared process-identity helpers for local platform PID files.
#
# Windows recycles process IDs. After a crash, a PID file can point at an
# unrelated program (for example a PostgreSQL backend that received the reused
# PID). A live PID alone is therefore not proof that a service is running:
# never stop a PID unless its identity matches the expected service script.

function Get-ServiceProcessState {
    param(
        [int]$ProcessId,
        [string[]]$ExpectedProcessNames = @("python", "pythonw"),
        [string]$ExpectedScript
    )

    if ($ProcessId -le 0) {
        return [pscustomobject]@{ Exists = $false; Matches = $false; ProcessName = $null; CommandLine = $null }
    }

    # Get-Process works for service-account processes whose command line is not
    # readable, so a non-Python process name is enough to prove PID reuse.
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return [pscustomobject]@{ Exists = $false; Matches = $false; ProcessName = $null; CommandLine = $null }
    }

    $nameMatches = @($ExpectedProcessNames | Where-Object { $process.ProcessName -like $_ }).Count -gt 0
    if (-not $nameMatches) {
        return [pscustomobject]@{ Exists = $true; Matches = $false; ProcessName = $process.ProcessName; CommandLine = $null }
    }

    $commandLine = $null
    try {
        $record = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if ($record -and $record.CommandLine) {
            $commandLine = [string]$record.CommandLine
        }
    } catch {
        $commandLine = $null
    }

    if (-not $commandLine) {
        # The process name matches but the command line is unreadable (another
        # account): report "unknown" instead of claiming the service is ours.
        return [pscustomobject]@{ Exists = $true; Matches = $null; ProcessName = $process.ProcessName; CommandLine = $null }
    }

    if ($ExpectedScript -and $commandLine -notlike "*$ExpectedScript*") {
        return [pscustomobject]@{ Exists = $true; Matches = $false; ProcessName = $process.ProcessName; CommandLine = $commandLine }
    }

    return [pscustomobject]@{ Exists = $true; Matches = $true; ProcessName = $process.ProcessName; CommandLine = $commandLine }
}
