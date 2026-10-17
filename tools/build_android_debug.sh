#!/usr/bin/env bash
# Reproducible local/CI debug build. Never reports success without a verified APK.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/tools/android_preflight.py" --strict
: "${ANDROID_HOME:=${ANDROID_SDK_ROOT:-}}"
: "${ANDROID_HOME:?Set ANDROID_HOME to Android SDK with build-tools 35.0.0}"
command -v gradle >/dev/null || { echo 'Gradle 8.9 must be installed' >&2; exit 1; }
gradle --version | grep -q '^Gradle 8.9$' || { echo 'Expected Gradle 8.9' >&2; exit 1; }
cd "$ROOT/android"
gradle --no-daemon --stacktrace :app:testDebugUnitTest :app:assembleDebug
cd "$ROOT"
source_apk="$ROOT/android/app/build/outputs/apk/debug/app-debug.apk"
test -s "$source_apk" || { echo 'APK not generated' >&2; exit 1; }
mkdir -p "$ROOT/artifacts"
target_apk="$ROOT/artifacts/AI-Remote-Control-v2.11-PLAYER-LAB.apk"
cp "$source_apk" "$target_apk"
python3 "$ROOT/tools/apk_release_gate.py" --apk "$target_apk" --out "$ROOT/artifacts/APK_ATTESTATION_v2.11.json"
echo "VERIFIED debug APK: $target_apk"
