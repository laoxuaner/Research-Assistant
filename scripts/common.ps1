Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:WorkbenchRoot = Split-Path -Parent $PSScriptRoot

function Assert-NativeExit {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
}

function Find-WorkbenchPython {
    param([string]$Python = '')
    if ($Python) {
        $resolved = Get-Command -Name $Python -CommandType Application -ErrorAction Stop | Select-Object -First 1
        return [pscustomobject]@{ Path = $resolved.Source; Prefix = @() }
    }
    $pyLauncher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pyLauncher) {
        try {
            & $pyLauncher.Source -3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' *> $null
            if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ Path = $pyLauncher.Source; Prefix = @('-3') } }
        } catch { # An installed launcher may have no installed Python runtime.
        }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $candidate = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($candidate -and $candidate.Source -notlike '*WindowsApps*') {
            try {
                & $candidate.Source -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' *> $null
                if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ Path = $candidate.Source; Prefix = @() } }
            } catch { # Continue to the bundled runtime.
            }
        }
    }
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return [pscustomobject]@{ Path = $bundled; Prefix = @() }
    }
    throw 'Python 3.12+ not found. Install CPython, or pass -Python "C:\path with spaces\python.exe".'
}

function Find-WorkbenchNode {
    param([string]$Node = '')
    if ($Node) { return (Get-Command $Node -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }
    $candidate = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { return $candidate.Source }
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    throw 'Node.js 20+ not found. Install Node.js, or pass -Node "C:\path\node.exe".'
}

function Find-WorkbenchNpm {
    param([string]$Npm = '')
    if ($Npm) { return (Get-Command $Npm -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }
    $candidate = Get-Command npm.cmd -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { return $candidate.Source }
    throw 'npm.cmd not found. Install Node.js with npm, or pass -Npm "C:\path\npm.cmd".'
}

function Get-WorkbenchVenvPython {
    $pythonExe = Join-Path $script:WorkbenchRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw 'Virtual environment missing. Run .\scripts\setup.ps1 first.'
    }
    return $pythonExe
}
