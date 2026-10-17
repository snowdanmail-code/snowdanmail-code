package com.example.airemote
import java.util.ArrayDeque

/** Offline, bounded RTT telemetry. These samples DO NOT verify an in-app poker timer. */
class LatencyWindow(private val capacity: Int = 50) {
    init { require(capacity in 1..1000) }
    private val values = ArrayDeque<Long>()
    @Synchronized fun record(rttMs: Long) {
        require(rttMs in 0L..120000L)
        if (values.size == capacity) values.removeFirst()
        values.addLast(rttMs)
    }
    @Synchronized fun percentile95(): Long? {
        if (values.isEmpty()) return null
        val sorted = values.sorted()
        val index = kotlin.math.ceil(sorted.size * 0.95).toInt().coerceAtLeast(1) - 1
        return sorted[index]
    }
    @Synchronized fun count(): Int = values.size
}
