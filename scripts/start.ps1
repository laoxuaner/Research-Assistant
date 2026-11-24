[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
try {
    $pythonExe = Get-WorkbenchVenvPython
    if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
        throw 'Frontend build missing. Run .\scripts\setup.ps1 or npm run build in frontend.'
    }
    Write-Host "Research workbench: http://127.0.0.1:8000 ; Ctrl+C to stop."
    & $pythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
    Assert-NativeExit 'Run application'
} finally { Pop-Location }
