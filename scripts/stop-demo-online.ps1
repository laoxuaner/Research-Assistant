[CmdletBinding()]
param([switch]$StatusOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$tmpRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'tmp'))
$sessionFile = Join-Path $tmpRoot 'online-demo-session.json'
$mutexHash = [Security.Cryptography.SHA256]::Create()
try { $mutexName = 'Local\ResearchAssistantOnlineDemo_' + ([BitConverter]::ToString($mutexHash.ComputeHash([Text.Encoding]::UTF8.GetBytes($tmpRoot.ToLowerInvariant())))).Replace('-', '') }
finally { $mutexHash.Dispose() }
$mutex = New-Object Threading.Mutex($false, $mutexName)
$locked = $false

function Get-VerifiedDemoProcess {
    param([int]$ProcessId, [string]$Executable, [string]$StartTicks, [string]$RequiredArgument)
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    $identity = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $ProcessId) -ErrorAction Stop
    if (-not $identity -or -not $identity.ExecutablePath -or -not $identity.CommandLine -or
        $process.StartTime.ToUniversalTime().Ticks -ne [long]$StartTicks -or
        -not [IO.Path]::GetFullPath($identity.ExecutablePath).Equals([IO.Path]::GetFullPath($Executable), [StringComparison]::OrdinalIgnoreCase) -or
        $identity.CommandLine.IndexOf($RequiredArgument, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw ('Process identity no longer matches the recorded demo session (PID ' + $ProcessId + '). No unrelated process will be stopped.')
    }
    return $process
}

try {
    try { $locked = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another demo start/stop operation is in progress. Try again after it finishes.' }
    if (-not (Test-Path -LiteralPath $sessionFile)) {
        if ($StatusOnly) { return [pscustomobject]@{ Active = $false; Partial = $false; Url = $null; RunDirectory = $null } }
        Write-Host 'No temporary demo session is recorded.'
        return
    }
    $state = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
    $runDirectory = [IO.Path]::GetFullPath([string]$state.run_directory)
    $serverScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'start_demo.py'))
    $serverExe = [IO.Path]::GetFullPath((Join-Path $projectRoot '.venv/Scripts/python.exe'))
    if (-not $runDirectory.StartsWith($tmpRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFullPath([string]$state.server_script).Equals($serverScript, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFullPath([string]$state.server_executable).Equals($serverExe, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName([string]$state.tunnel_executable) -notlike 'cloudflared*.exe' -or
        [string]$state.url -notmatch '^https://[a-z0-9-]+\.trycloudflare\.com$' -or
        [string]$state.local_url -notmatch '^http://127\.0\.0\.1:[0-9]{4,5}$' -or
        [int]$state.tunnel_pid -le 0 -or [int]$state.server_pid -le 0) {
        throw 'The saved demo session contains unexpected paths or process metadata. No process was stopped.'
    }
    $tunnel = Get-VerifiedDemoProcess -ProcessId $state.tunnel_pid -Executable $state.tunnel_executable -StartTicks $state.tunnel_start_ticks -RequiredArgument $state.local_url
    $server = Get-VerifiedDemoProcess -ProcessId $state.server_pid -Executable $serverExe -StartTicks $state.server_start_ticks -RequiredArgument $serverScript
    if ($StatusOnly) {
        return [pscustomobject]@{ Active = ($null -ne $tunnel -and $null -ne $server); Partial = (($null -ne $tunnel) -xor ($null -ne $server)); Url = $state.url; RunDirectory = $runDirectory }
    }
    # Windows virtual environments can use a Python redirector parent. Only stop
    # a directly owned Python child whose command and creation time also match.
    if ($server) {
        $born = $server.StartTime.ToUniversalTime().Ticks
        foreach ($child in @(Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $server.Id) -ErrorAction Stop)) {
            if ($child.Name -notin @('python.exe', 'pythonw.exe') -or -not $child.CommandLine -or
                $child.CommandLine.IndexOf($serverScript, [StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
            $childProcess = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($childProcess -and $child.CreationDate -and $child.ExecutablePath -and
                $child.CreationDate.ToUniversalTime().Ticks -ge $born -and
                [Math]::Abs($childProcess.StartTime.ToUniversalTime().Ticks - $child.CreationDate.ToUniversalTime().Ticks) -lt 10 -and
                $childProcess.Path.Equals($child.ExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
                Stop-Process -InputObject $childProcess -Force -ErrorAction Stop
            }
        }
    }
    foreach ($process in @($server, $tunnel)) {
        if ($null -ne $process) {
            $process.Refresh()
            if (-not $process.HasExited) { Stop-Process -InputObject $process -Force -ErrorAction Stop }
        }
    }
    Remove-Item -LiteralPath $sessionFile -Force
    Write-Host 'Temporary demo stopped. Original local data and the isolated demo run files have been retained.'
    Write-Host ('Retained demo logs and data: ' + $runDirectory)
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
