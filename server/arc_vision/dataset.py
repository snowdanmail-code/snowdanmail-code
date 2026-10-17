"""Integrity checks for manually reviewed video-frame fixtures.

This module makes no claim to classify novel images.
"""
import hashlib
import json
from pathlib import Path

LABELS = frozenset({
    "LIVE_TABLE", "PRE_ACTION", "ACTIVE_ACTION", "BET_SIZING",
    "SHOWDOWN", "OVERLAY_SESSION_STATS", "OVERLAY_WAITLIST",
    "OVERLAY_HAND_HISTORY",
})

def load_manifest(dataset_dir):
    p = Path(dataset_dir) / "manifest.json"
    payload = json.loads(p.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported fixture manifest schema")
    return payload

def validate_manifest(dataset_dir):
    root = Path(dataset_dir).resolve()
    doc = load_manifest(root)
    seen = set()
    for entry in doc["entries"]:
        if entry["id"] in seen:
            raise ValueError("Duplicate frame id")
        seen.add(entry["id"])
        if entry["label"] not in LABELS:
            raise ValueError("Unknown frame label")
        rel = Path(entry["image"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe fixture path")
        image = (root / rel).resolve()
        if not image.is_relative_to(root) or not image.is_file():
            raise ValueError("Missing fixture image")
        if hashlib.sha256(image.read_bytes()).hexdigest() != entry["image_sha256"]:
            raise ValueError("Fixture checksum mismatch")
    return len(seen)
