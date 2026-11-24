[CmdletBinding()]
param([switch]$E2E, [switch]$InstallBrowsers, [string]$Node = '', [string]$Npm = '')
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
try {
    $pythonExe = Get-WorkbenchVenvPython
    & $pythonExe -m pytest backend/tests -q -p no:cacheprovider
    Assert-NativeExit 'Backend tests'
    $nodeExe = Find-WorkbenchNode -Node $Node
    $npmExe = Find-WorkbenchNpm -Npm $Npm
    $env:PATH = (Split-Path -Parent $nodeExe) + [IO.Path]::PathSeparator + $env:PATH
    Push-Location (Join-Path $script:WorkbenchRoot 'frontend')
    try {
        & $npmExe run build
        Assert-NativeExit 'Frontend production build'
        if ($E2E) {
            if ($InstallBrowsers) {
                & $nodeExe node_modules/@playwright/test/cli.js install chromium
                Assert-NativeExit 'Install Playwright Chromium'
            }
            & $npmExe run test:e2e
            Assert-NativeExit 'Browser tests'
        }
    } finally { Pop-Location }
} finally { Pop-Location }
