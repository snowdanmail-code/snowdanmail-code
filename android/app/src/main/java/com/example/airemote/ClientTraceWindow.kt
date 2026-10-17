package com.example.airemote

import java.util.ArrayDeque

/**
 * Phone-only capture-to-response latency telemetry. All timestamps must come
 * from the SAME SystemClock.elapsedRealtime() domain; never mix server time.
 * This class is read-only telemetry; a fresh response is not an execution permit.
 */
class ClientTraceWindow(private val capacity: Int = 100, private val maxFrameAgeMs: Long = 1300L) {
    init { require(capacity in 1..1000 && maxFrameAgeMs in 1..120000) }
    private val samples = ArrayDeque<Long>()
    private var newestSequence = -1L
    private var latestReason = "NO_SAMPLE"

    @Synchronized fun onFrame(sequence: Long) {
        require(sequence >= 0)
        if (sequence > newestSequence) newestSequence = sequence
    }

    @Synchronized fun onResponse(sequence: Long, captureMs: Long, nowMs: Long): String {
        require(sequence >= 0 && captureMs >= 0 && nowMs >= 0)
        val reason = when {
            nowMs < captureMs -> "CLOCK_REGRESSION"
            sequence < newestSequence -> "SUPERSEDED"
            nowMs - captureMs > maxFrameAgeMs -> "STALE_RESPONSE"
            else -> "FRESH_OBSERVATION_ONLY"
        }
        latestReason = reason
        if (nowMs >= captureMs) {
            if (samples.size == capacity) samples.removeFirst()
            samples.addLast(nowMs - captureMs)
        }
        return reason
    }

    @Synchronized fun p95Ms(): Long? {
        if (samples.isEmpty()) return null
        val sorted = samples.sorted()
        return sorted[(kotlin.math.ceil(sorted.size * .95).toInt() - 1).coerceAtLeast(0)]
    }
    @Synchronized fun count(): Int = samples.size
    @Synchronized fun lastReason(): String = latestReason
    fun grantsMoneyActions(): Boolean = false
}
