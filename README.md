# VPN Visibility (experimental)

This LSPosed/Xposed module changes select Java VPN-status API results only inside applications explicitly chosen as its LSPosed scope. VPN stays active and network routing is not changed. It does NOT hide the external IP, DNS or native-level checks; compatibility with Android 16 / VK is untested.

Requires root + compatible LSPosed. Without root this APK cannot intercept other apps' Android calls. Do not scope to Android Framework, SystemUI or system services.

After install, select com.vkontakte.android in LSPosed module scope, restart VK, test. To reverse, disable module and restart app. Rooting Samsung may permanently trip Knox.

Built via GitHub Actions. Download artifact ZIP -> app-debug.apk. No network permissions or user-interface launcher activity.
