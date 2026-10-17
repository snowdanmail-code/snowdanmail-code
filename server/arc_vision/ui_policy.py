"""Observability only: hard-stop policy for ambiguous/capped interface frames.

These guards never authorize monetary action.
"""
from enum import Enum

class FrameCategory(str, Enum):
    LIVE_TABLE = "LIVE_TABLE"
    PRE_ACTION = "PRE_ACTION"
    ACTIVE_ACTION = "ACTIVE_ACTION"
    BET_SIZING = "BET_SIZING"
    SHOWDOWN = "SHOWDOWN"
    OVERLAY_SESSION_STATS = "OVERLAY_SESSION_STATS"
    OVERLAY_WAITLIST = "OVERLAY_WAITLIST"
    OVERLAY_HAND_HISTORY = "OVERLAY_HAND_HISTORY"
    UNKNOWN = "UNKNOWN"

def interpret_frame(category, active_table=True, playback_mode=False, connection_ok=True):
    if not connection_ok:
        return {"status": "CONNECTION_LOST", "allow_active_commands": False, "post_session_review": False}
    if playback_mode:
        return {"status": "REPLAY", "allow_active_commands": False, "post_session_review": False}
    if category in {FrameCategory.OVERLAY_SESSION_STATS, FrameCategory.OVERLAY_WAITLIST,
                    FrameCategory.OVERLAY_HAND_HISTORY}:
        return {"status": "OVERLAY", "allow_active_commands": False, "post_session_review": False}
    if category == FrameCategory.UNKNOWN:
        return {"status": "UNKNOWN", "allow_active_commands": False, "post_session_review": False}
    # Always observe-only; this module cannot initiate a financial interaction.
    return {"status": category.value, "allow_active_commands": False, "post_session_review": False}

def can_review_history(*, confirmed_zero_open_tables, any_active_session, state_is_known):
    return bool(confirmed_zero_open_tables and not any_active_session and state_is_known)
