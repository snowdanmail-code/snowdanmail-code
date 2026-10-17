#!/usr/bin/env python3
"""Fail-closed Android *debug* APK verification.

Requires a REAL APK produced by Android Gradle Plugin, SDK 35 aapt and
apksigner. This tool does not build, sign, install or execute an APK.
It is not a substitute for tests on an Android device.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable

PACKAGE = "com.example.airemote"
VERSION_CODE = "31"
VERSION_NAME = "2.11.0-persistent-stop"
APK_NAME = "AI-Remote-Control-v2.11-PLAYER-LAB.apk"
SDK_BUILD_TOOLS = "35.0.0"


class ApkGateError(RuntimeError):
    pass


def tool_path(tool: str, sdk: str | None = None) -> str:
    root = sdk or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not root:
        raise ApkGateError("ANDROID_HOME or ANDROID_SDK_ROOT is required")
    executable = tool + (".bat" if os.name == "nt" and tool == "apksigner" else (".exe" if os.name == "nt" else ""))
    p = Path(root) / "build-tools" / SDK_BUILD_TOOLS / executable
    if not p.is_file():
        raise ApkGateError(f"Missing Android SDK build tool: {p}")
    return str(p)


def _run(command: list[str], runner: Callable = subprocess.run) -> str:
    try:
        result = runner(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApkGateError(f"Could not run {Path(command[0]).name}: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise ApkGateError(f"{Path(command[0]).name} failed with exit code {result.returncode}: {(result.stderr or '')[:300]}")
    return result.stdout


def inspect(apk: Path, aapt: str, apksigner: str, runner: Callable = subprocess.run) -> dict:
    if not apk.is_file() or apk.stat().st_size < 100:
        raise ApkGateError("APK missing or implausibly small")
    try:
        with zipfile.ZipFile(apk) as z:
            required = {"AndroidManifest.xml", "classes.dex", "resources.arsc"}
            if not required.issubset(set(z.namelist())):
                raise ApkGateError("APK is missing AndroidManifest.xml, classes.dex or resources.arsc")
            corrupt = z.testzip()
            if corrupt is not None:
                raise ApkGateError(f"Corrupt APK ZIP entry: {corrupt}")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ApkGateError("APK is not a readable ZIP archive") from exc

    badging = _run([aapt, "dump", "badging", str(apk)], runner)
    pkg = re.search(r"^package:\s+name='([^']+)'\s+versionCode='([^']+)'\s+versionName='([^']+)'", badging, re.M)
    if not pkg:
        raise ApkGateError("aapt did not return valid package/version metadata")
    if pkg.groups() != (PACKAGE, VERSION_CODE, VERSION_NAME):
        raise ApkGateError(f"Unexpected APK identity/version: {pkg.groups()}")
    if not re.search(r"^application-debuggable\s*$", badging, re.M):
        raise ApkGateError("Expected a debug-only APK, but debuggable flag was not found")
    min_sdk = re.search(r"^sdkVersion:'(\d+)'", badging, re.M)
    target_sdk = re.search(r"^targetSdkVersion:'(\d+)'", badging, re.M)
    if not min_sdk or min_sdk.group(1) != "29" or not target_sdk or target_sdk.group(1) != "35":
        raise ApkGateError("APK SDK version mismatch (expected min=29, target=35)")
    signature = _run([apksigner, "verify", "--verbose", "--print-certs", str(apk)], runner)
    if not re.search(r"^Verified\s+using\s+v[234]\s+scheme\s+\(APK Signature Scheme v[234]\):\s+true\s*$", signature, re.M):
        raise ApkGateError("No verified modern Android APK signature scheme")
    if not re.search(r"^Signer #1 certificate SHA-256 digest:\s*[0-9a-fA-F]{64}\s*$", signature, re.M):
        raise ApkGateError("APK signer certificate digest missing")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    return {
        "status": "VERIFIED_DEBUG_APK",
        "artifact": apk.name,
        "sha256": digest,
        "size_bytes": apk.stat().st_size,
        "package": PACKAGE,
        "version_code": int(VERSION_CODE),
        "version_name": VERSION_NAME,
        "min_sdk": 29,
        "target_sdk": 35,
        "signature_verified": True,
        "debuggable": True,
        "source_preflight_required": True,
        "installed_or_tested_on_device": False,
        "real_money_transactions": False,
        "note": "External-action switch is checked by source preflight, not inferred from the APK binary. No device execution is claimed."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--aapt")
    parser.add_argument("--apksigner")
    args = parser.parse_args()
    try:
        aapt = args.aapt or tool_path("aapt")
        apksigner = args.apksigner or tool_path("apksigner")
        report = inspect(args.apk, aapt, apksigner)
    except ApkGateError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.out.parent / (args.apk.name + ".sha256")).write_text(
            f"{report['sha256']}  {args.apk.name}\n", encoding="ascii")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
