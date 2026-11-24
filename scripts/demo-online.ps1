[CmdletBinding()]
param(
    [string]$Cloudflared = '',
    [ValidateRange(1024, 65535)][int]$Port = 8010,
    [ValidateRange(20, 300)][int]$StartupTimeoutSeconds = 120
)

. (Join-Path $PSScriptRoot 'common.ps1')
$tmpRoot = [IO.Path]::GetFullPath((Join-Path $script:WorkbenchRoot 'tmp'))
$sessionFile = Join-Path $tmpRoot 'online-demo-session.json'
$stopScript = Join-Path $PSScriptRoot 'stop-demo-online.ps1'
$serverScript = Join-Path $PSScriptRoot 'start_demo.py'
$expectedSha = '2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343'
$mutexHash = [Security.Cryptography.SHA256]::Create()
try { $mutexName = 'Local\ResearchAssistantOnlineDemo_' + ([BitConverter]::ToString($mutexHash.ComputeHash([Text.Encoding]::UTF8.GetBytes($tmpRoot.ToLowerInvariant())))).Replace('-', '') }
finally { $mutexHash.Dispose() }
$mutex = New-Object Threading.Mutex($false, $mutexName)
$locked = $false
$started = $false
$tunnelProcess = $null
$serverProcess = $null
$sessionWritten = $false
$savedEnvironment = @{}

function Stop-CreatedProcess {
    param([Diagnostics.Process]$Process, [string]$ChildScript = '')
    if ($null -eq $Process) { return }
    try {
        $Process.Refresh()
        if ($Process.HasExited) { return }
        $born = $Process.StartTime.ToUniversalTime().Ticks
        if ($ChildScript) {
            $children = @(Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $Process.Id) -ErrorAction Stop)
            foreach ($child in $children) {
                if ($child.Name -notin @('python.exe', 'pythonw.exe') -or -not $child.CommandLine -or
                    $child.CommandLine.IndexOf($ChildScript, [StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
                $liveChild = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
                if ($liveChild -and $child.CreationDate -and $child.ExecutablePath -and
                    $child.CreationDate.ToUniversalTime().Ticks -ge $born -and
                    [Math]::Abs($liveChild.StartTime.ToUniversalTime().Ticks - $child.CreationDate.ToUniversalTime().Ticks) -lt 10 -and
                    $liveChild.Path.Equals($child.ExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
                    Stop-Process -InputObject $liveChild -Force -ErrorAction Stop
                }
            }
        }
        $Process.Refresh()
        if (-not $Process.HasExited) { Stop-Process -InputObject $Process -Force -ErrorAction Stop }
    } catch { Write-Warning 'A process created by this start attempt could not be stopped. Inspect the run logs and process status.' }
}

try {
    try { $locked = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another demo start/stop operation is in progress. Try again after it finishes.' }
    if (Test-Path -LiteralPath $sessionFile) {
        $current = & $stopScript -StatusOnly
        if ($current.Active) {
            Write-Host ('Temporary demo is already running: ' + $current.Url)
            Write-Host ('Logs and demo data: ' + $current.RunDirectory)
            return
        }
        & $stopScript
    }
    $pythonExe = Get-WorkbenchVenvPython
    if (-not (Test-Path -LiteralPath (Join-Path $script:WorkbenchRoot 'frontend/dist/index.html'))) {
        throw 'Frontend build is missing. Run .\scripts\setup.ps1 first.'
    }
    if (-not $Cloudflared) { $Cloudflared = Join-Path $tmpRoot 'tools/cloudflared-2026.10.7.exe' }
    if (-not (Test-Path -LiteralPath $Cloudflared -PathType Leaf)) {
        throw ('cloudflared is missing. Download cloudflared-windows-amd64.exe from https://github.com/cloudflare/cloudflared/releases/tag/2026.10.7 and save it as ' + $Cloudflared + '. Expected SHA256: ' + $expectedSha)
    }
    $cloudflaredExe = (Get-Item -LiteralPath $Cloudflared).FullName
    if ([IO.Path]::GetFileName($cloudflaredExe) -notlike 'cloudflared*.exe') { throw 'Cloudflared must point at a cloudflared*.exe executable.' }
    if ([IO.Path]::GetFileName($cloudflaredExe) -eq 'cloudflared-2026.10.7.exe' -and
        (Get-FileHash -LiteralPath $cloudflaredExe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha) {
        throw 'cloudflared 2026.10.7 SHA256 does not match the official release.'
    }
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $Port)
    try { $listener.Start() }
    catch { throw ('Port ' + $Port + ' is already in use. Choose another port with -Port.') }
    finally { $listener.Stop() }

    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $runDirectory = [IO.Path]::GetFullPath((Join-Path $tmpRoot ('online-demo-runs/' + $runId)))
    if (-not $runDirectory.StartsWith($tmpRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid demo run directory.' }
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    $localUrl = 'http://127.0.0.1:' + $Port
    $tunnelOut = Join-Path $runDirectory 'tunnel.stdout.log'
    $tunnelErr = Join-Path $runDirectory 'tunnel.stderr.log'
    $tunnelProcess = Start-Process -FilePath $cloudflaredExe -ArgumentList @('--no-autoupdate', 'tunnel', '--url', $localUrl, '--protocol', 'http2', '--edge-ip-version', '4') -WorkingDirectory $runDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr
    $publicUrl = $null
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $tunnelProcess.Refresh()
        if ($tunnelProcess.HasExited) { throw ('cloudflared stopped. See ' + $tunnelErr) }
        $logs = ''
        foreach ($logFile in @($tunnelOut, $tunnelErr)) {
            if (Test-Path -LiteralPath $logFile) {
                $sharedLog = [IO.FileStream]::new($logFile, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
                $logReader = [IO.StreamReader]::new($sharedLog)
                try { $logs += $logReader.ReadToEnd() + "`n" }
                finally { $logReader.Dispose() }
            }
        }
        $match = [regex]::Match($logs, 'https://[a-z0-9-]+\.trycloudflare\.com\b')
        if ($match.Success) { $publicUrl = $match.Value; break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $publicUrl) { throw ('Timed out waiting for the temporary URL. See ' + $tunnelErr) }

    $demoEnvironment = @{ PUBLIC_URL = $publicUrl; PORT = [string]$Port; DEMO_BIND_HOST = '127.0.0.1'; DEMO_DATA_DIR = (Join-Path $runDirectory 'data') }
    foreach ($name in $demoEnvironment.Keys) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $demoEnvironment[$name], 'Process')
    }
    $serverProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-u', ('"' + $serverScript + '"')) -WorkingDirectory $script:WorkbenchRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDirectory 'server.stdout.log') -RedirectStandardError (Join-Path $runDirectory 'server.stderr.log')
    $state = [ordered]@{
        url = $publicUrl; local_url = $localUrl; run_directory = $runDirectory
        tunnel_pid = $tunnelProcess.Id; tunnel_executable = $cloudflaredExe; tunnel_start_ticks = [string]$tunnelProcess.StartTime.ToUniversalTime().Ticks
        server_pid = $serverProcess.Id; server_executable = $pythonExe; server_script = $serverScript; server_start_ticks = [string]$serverProcess.StartTime.ToUniversalTime().Ticks
    }
    $stateTemporary = Join-Path $runDirectory 'session.json'
    $state | ConvertTo-Json | Set-Content -LiteralPath $stateTemporary -Encoding UTF8
    Move-Item -LiteralPath $stateTemporary -Destination $sessionFile -Force
    $sessionWritten = $true
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $serverProcess.Refresh(); $tunnelProcess.Refresh()
        if ($serverProcess.HasExited -or $tunnelProcess.HasExited) { throw ('A demo process stopped. Inspect logs in ' + $runDirectory) }
        try {
            $health = Invoke-RestMethod -Uri ($localUrl + '/api/health') -TimeoutSec 2
            $settings = Invoke-RestMethod -Uri ($localUrl + '/api/settings') -TimeoutSec 2
            if ($health.status -eq 'ok' -and $settings.read_only -eq $true -and $settings.deployment_mode -eq 'demo') { $ready = $true; break }
        } catch { # The isolated demo imports and parses its synthetic fixtures on first start.
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw ('Demo startup timed out. Inspect logs in ' + $runDirectory) }
    $started = $true
    Write-Host ('Temporary public demo: ' + $publicUrl)
    Write-Host 'Keep this computer awake and connected to the internet. The URL is temporary; this is a read-only demo with synthetic data.'
    Write-Host ('Logs and isolated demo data: ' + $runDirectory)
    Write-Host 'Stop with: .\scripts\stop-demo-online.ps1'
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    if (-not $started) {
        Stop-CreatedProcess -Process $serverProcess -ChildScript $serverScript
        Stop-CreatedProcess -Process $tunnelProcess
        if ($sessionWritten -and (Test-Path -LiteralPath $sessionFile)) { Remove-Item -LiteralPath $sessionFile -Force }
    }
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
