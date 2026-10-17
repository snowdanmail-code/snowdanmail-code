# Requires Android platform-tools and USB debugging approval on user's phone.
param([switch]$InstallApk)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$adb = Get-Command adb.exe -ErrorAction SilentlyContinue
if (-not $adb) {
    $sdk = $env:ANDROID_HOME
    if (-not $sdk) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    $candidate = Join-Path $sdk 'platform-tools\adb.exe'
    if (Test-Path $candidate) { $adb = Get-Item $candidate }
}
if (-not $adb) { throw 'adb.exe is missing. Install Android SDK Platform-Tools.' }
$exe=$adb.FullName
$devices=(& $exe devices | Out-String)
Write-Host $devices
if ($devices -notmatch '(?m)^\S+\s+device\s*$') { throw 'Connect phone via USB and accept Allow USB debugging on the phone.' }
& $exe reverse tcp:8787 tcp:8787
if ($LASTEXITCODE -ne 0) { throw 'ADB reverse failed.' }
$map=(& $exe reverse --list | Out-String)
if ($map -notmatch 'tcp:8787') { throw 'ADB reverse mapping was not verified.' }
Write-Host ('ADB REVERSE OK: ' + $map) -ForegroundColor Green
if ($InstallApk) {
    $apk=Join-Path $root 'artifacts\AI-Remote-Control-v2.12-PLAYER-LAB.apk'
    if (-not (Test-Path $apk)) { throw 'APK not found. Build with 01_BUILD_APK.ps1 first.' }
    & $exe install -r $apk
    if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
    Write-Host 'Lab APK installed. Enable MediaProjection and test Accessibility in app manually.'
}
Write-Host 'Android server URL: http://127.0.0.1:8787'
Write-Host 'No external app touches or wagers in this LAB APK.'
