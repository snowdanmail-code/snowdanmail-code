package com.example.airemote

import kotlin.math.ceil

/** Pure Kotlin, independent of Android and networking. RTT is not end-to-end model latency. */
object RttSummary {
    data class Report(
        val successes: Int,
        val failures: Int,
        val medianMs: Long?,
        val p95Ms: Long?,
        val minimumMs: Long?,
        val maximumMs: Long?,
        val quality: String
    )

    fun fromSamples(successMs: List<Long>, failures: Int): Report {
        require(failures >= 0) { "Negative failure count" }
        require(successMs.size <= 100) { "Too many samples" }
        require(successMs.all { it >= 0 && it <= 120_000 }) { "Invalid RTT" }
        val sorted = successMs.sorted()
        if (sorted.isEmpty()) return Report(0, failures, null, null, null, null, "NO_CONNECTION")
        val median = if (sorted.size % 2 == 1) {
            sorted[sorted.size / 2]
        } else {
            (sorted[sorted.size / 2 - 1] + sorted[sorted.size / 2]) / 2
        }
        val p95Index = ceil(sorted.size * 0.95).toInt().coerceAtLeast(1) - 1
        val p95 = sorted[p95Index]
        val quality = when {
            sorted.size < 3 || failures > 0 -> "UNSTABLE_OR_INSUFFICIENT"
            p95 <= 150 -> "LOW_RTT"
            p95 <= 500 -> "MODERATE_RTT"
            else -> "HIGH_RTT"
        }
        return Report(sorted.size, failures, median, p95, sorted.first(), sorted.last(), quality)
    }
}
