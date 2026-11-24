[CmdletBinding()]
param([string]$Node = '')
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
$backendProcess = $null
$frontendProcess = $null
try {
    $pythonExe = Get-WorkbenchVenvPython
    $nodeExe = Find-WorkbenchNode -Node $Node
    $viteFile = Join-Path $script:WorkbenchRoot 'frontend/node_modules/vite/bin/vite.js'
    if (-not (Test-Path -LiteralPath $viteFile)) { throw 'Frontend dependencies missing. Run setup.ps1 first.' }
    $logDir = Join-Path $script:WorkbenchRoot 'data/dev-logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $backendArgs = @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000','--reload')
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList $backendArgs -WorkingDirectory $script:WorkbenchRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') -RedirectStandardError (Join-Path $logDir 'backend.stderr.log')
    $frontendArgs = @(('"' + $viteFile + '"'), '--host','127.0.0.1','--port','5173','--strictPort')
    $frontendProcess = Start-Process -FilePath $nodeExe -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $script:WorkbenchRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend.stdout.log') -RedirectStandardError (Join-Path $logDir 'frontend.stderr.log')
    Write-Host 'Development UI: http://127.0.0.1:5173 ; API: http://127.0.0.1:8000'
    Write-Host "Logs: $logDir ; Ctrl+C stops the processes started by this script."
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Seconds 1
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
    }
    throw "A development server stopped. Inspect $logDir."
} finally {
    foreach ($process in @($backendProcess, $frontendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
    Pop-Location
}
