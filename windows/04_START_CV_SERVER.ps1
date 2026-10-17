# Start from a trusted local copy of the source project, Python 3.11+ installed.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path '.venv-cv\Scripts\python.exe')) {
    py -3 -m venv .venv-cv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3 is required.' }
}
$python = Join-Path $root '.venv-cv\Scripts\python.exe'
& $python -m pip install -r server\requirements-vision.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install CV dependencies.' }
& $python tools\start_local_server.py
