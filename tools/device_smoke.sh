#!/usr/bin/env bash
set -euo pipefail
# CI-only synthetic token, local server; no external services or account.
ARC_DEVICE_TOKEN=synthetic-android-cv-test ARC_PORT=18787 OPENAI_API_KEY='' ARC_ENABLE_POKER_ACTIONS=0 python3 server/server.py > /tmp/arc-device-server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT
python3 - <<'PY'
import time,urllib.request
for _ in range(40):
    try:
        urllib.request.urlopen('http://127.0.0.1:18787/health',timeout=1);break
    except OSError:time.sleep(.2)
else:raise SystemExit('Real CV backend failed to start')
PY
adb reverse tcp:18787 tcp:18787
gradle -p android --no-daemon :app:connectedDebugAndroidTest
adb shell am force-stop com.example.airemote.v212
adb shell am start -W -n com.example.airemote.v212/com.example.airemote.MainActivity
adb shell pidof com.example.airemote.v212
adb exec-out screencap -p > artifacts/Android16-v2.12-launch.png
