# VPN Visibility v0.2 (experimental)

Launcher icon and informational screen added. Android launcher now shows VPN Visibility.

This is an LSPosed/Xposed module that selectively overrides Java VPN detection APIs in chosen app processes. The VPN tunnel stays enabled, and traffic is not rerouted. Does NOT hide VPN server IP, DNS or native checks. Android 16 / VK runtime behavior is unverified.

Requirements: **root + compatible LSPosed**. Installing alone or pressing the launcher icon does not activate any hooks. Rooting Samsung may permanently trip Knox and wipe data.

Use LSPosed Manager > Modules > VPN Visibility > Enable > Scope > VK (com.vkontakte.android), then restart VK. Never scope to Android Framework or system services. To reverse, disable the module.

Built by GitHub Actions. Download the successful build's artifact ZIP, then install app-debug.apk. If installation as update fails because GitHub's debug signing key changed, uninstall the previous debug build and install again.

Disclaimer: experimental; test on a device you control. The application screen is for instructions only.
