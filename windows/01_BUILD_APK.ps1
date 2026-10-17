# AI Remote Control: Windows Lab APK build. Requires locally installed SDK/Gradle.
# No real-money actions are enabled in this build.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
Write-Host '=== AI Remote Control v2.12 (APK VERIFICATION) ==='
if (-not (Get-Command java.exe -ErrorAction SilentlyContinue)) { throw 'Java JDK 17 not found. Install Java 17 before building.' }
$versionText = (& java.exe -version 2>&1 | Out-String)
if ($versionText -notmatch 'version "17\.') { throw "Build requires Java 17. Found: $versionText" }
$Sdk = $env:ANDROID_HOME
if (-not $Sdk) { $Sdk = $env:ANDROID_SDK_ROOT }
if (-not $Sdk) { $Sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
if (-not (Test-Path (Join-Path $Sdk 'platforms\android-35\android.jar'))) {
    throw 'Missing Android SDK Platform 35. Install it using Android Studio > Settings > Android SDK.'
}
$env:ANDROID_HOME = $Sdk
$GradleCommand = Get-Command gradle.exe -ErrorAction SilentlyContinue
if (-not $GradleCommand) { $GradleCommand = Get-Command gradle.bat -ErrorAction SilentlyContinue }
if (-not $GradleCommand) { throw 'Gradle 8.9 missing. Install Gradle 8.9 or use GitHub Actions workflow from this project.' }
$GradleOutput = (& $GradleCommand.Source --version 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $GradleOutput -notmatch '(?m)^Gradle 8\.9\s*$') { throw 'Expected Gradle 8.9.' }
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3 required for mandatory APK verification' }
& $python.Source (Join-Path $ProjectRoot 'tools\android_preflight.py') --strict
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed' }
Push-Location (Join-Path $ProjectRoot 'android')
try {
    & $GradleCommand.Source --no-daemon :app:testDebugUnitTest :app:assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Gradle build failed. The APK is not ready.' }
} finally { Pop-Location }
$Source = Join-Path $ProjectRoot 'android\app\build\outputs\apk\debug\app-debug.apk'
if (-not (Test-Path $Source)) { throw 'Gradle finished but app-debug.apk is missing' }
$DestDir = Join-Path $ProjectRoot 'artifacts'; New-Item -Force -ItemType Directory $DestDir | Out-Null
$Dest = Join-Path $DestDir 'AI-Remote-Control-v2.12-PLAYER-LAB.apk'
Copy-Item -LiteralPath $Source -Destination $Dest -Force
& $python.Source (Join-Path $ProjectRoot 'tools\apk_release_gate.py') --apk $Dest --out (Join-Path $DestDir 'APK_ATTESTATION_v2.12.json')
if ($LASTEXITCODE -ne 0) { throw 'APK verification failed; do not install' }
$Hash = Get-FileHash -LiteralPath $Dest -Algorithm SHA256
Write-Host '=== VERIFIED APK READY ===' -ForegroundColor Green
Write-Host $Dest
Write-Host ('SHA256: ' + $Hash.Hash)
Write-Host 'External money/game actions: DISABLED (LAB).'
