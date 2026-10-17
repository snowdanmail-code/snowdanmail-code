package com.example.airemote

/** Pure Kotlin policy for selecting observations; no Android SDK dependency.
 * Never treats a fresh frame as permission for a tap or monetary action.
 */
object FastCapturePolicy {
    const val MAX_FRAME_AGE_MS = 1300L
    const val FAST_INTERVAL_MS = 500L
    const val STANDARD_INTERVAL_MS = 2500L

    fun shouldUpload(sequence: Long, previousSequence: Long,
                     capturedAtMs: Long, nowMs: Long, lastSentAtMs: Long,
                     fastMode: Boolean): Boolean {
        if (sequence <= previousSequence || capturedAtMs > nowMs || capturedAtMs < 0L) return false
        if (fastMode && nowMs - capturedAtMs > MAX_FRAME_AGE_MS) return false
        if (nowMs < lastSentAtMs) return false
        val interval = if (fastMode) FAST_INTERVAL_MS else STANDARD_INTERVAL_MS
        return nowMs - lastSentAtMs >= interval
    }
}
