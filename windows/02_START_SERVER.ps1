# Start the local-only backend for Android USB adb reverse. No real-money actions.
param([switch]$NoDependencies)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3.11+ required. Install from python.org and add python.exe to PATH.' }
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    & $python.Source -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python venv' }
}
if (-not $NoDependencies) {
    & $venvPython -m pip install -r (Join-Path $root 'server\requirements-vision.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot install required Python packages' }
}
$bytes=New-Object 'System.Byte[]' 24
$rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$env:ARC_DEVICE_TOKEN=([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
$env:ARC_PORT='8787'
$env:ARC_ENABLE_POKER_ACTIONS='0'
$env:ARC_MAX_SINGLE_WAGER_CHIPS='0'
$env:ARC_MAX_SESSION_WAGER_CHIPS='0'
Write-Host '========================================================'
Write-Host 'SERVER URL IN ANDROID APP: http://127.0.0.1:8787'
Write-Host ('DEVICE TOKEN (enter into Android app): ' + $env:ARC_DEVICE_TOKEN)
Write-Host ('OPENAI mode: ' + $(if ($env:OPENAI_API_KEY) {'ACTIVE, API CHARGES POSSIBLE'} else {'DEMO, NO API CHARGES'}))
Write-Host 'Only 127.0.0.1 is listening; USB adb reverse needed.'
Write-Host 'To stop server: press Ctrl+C. No real-money betting allowed.'
Write-Host '========================================================'
Push-Location (Join-Path $root 'server')
try { & $venvPython 'server.py' } finally { Pop-Location }
