package com.example.airemote

import java.util.ArrayDeque
import kotlin.math.ceil

/**
 * Local pacing for consented SCREEN OBSERVATIONS ONLY. Pure Kotlin/JVM.
 * RTT values are from SystemClock.elapsedRealtime() differences on the phone.
 * A healthy signal is not permission for an automated monetary action.
 */
class ObservationBackoff(
    private val windowSize: Int = 32,
    private val minSamples: Int = 10,
    private val degradedP95Ms: Long = 1800,
    private val severeP95Ms: Long = 3500
) {
    init {
        require(windowSize in 2..1000 && minSamples in 2..windowSize)
        require(degradedP95Ms in 100..60000 && severeP95Ms > degradedP95Ms && severeP95Ms <= 60000)
    }

    private val samples = ArrayDeque<Long>()
    private var consecutiveFailures: Int = 0
    private var recovering: Boolean = false
    private var recoverySuccesses: Int = 0
    private var transport: String = "unknown"

    @Synchronized fun onNetworkChange(next: String) {
        require(next in setOf("wifi", "cellular", "unknown"))
        if (next != transport) {
            transport = next
            samples.clear()
            consecutiveFailures = 0
            recovering = false
            recoverySuccesses = 0
        }
    }

    @Synchronized fun onSuccess(roundTripMs: Long) {
        require(roundTripMs in 0..60000)
        if (samples.size == windowSize) samples.removeFirst()
        samples.addLast(roundTripMs)
        consecutiveFailures = 0
        if (recovering) {
            recoverySuccesses++
            if (recoverySuccesses >= 3) {
                recovering = false
                recoverySuccesses = 0
            }
        }
    }

    @Synchronized fun onFailure() {
        if (consecutiveFailures < 16) consecutiveFailures++
        recoverySuccesses = 0
        if (consecutiveFailures >= 3) recovering = true
    }

    @Synchronized fun p95Ms(): Long? {
        if (samples.isEmpty()) return null
        val ordered = samples.sorted()
        return ordered[(ceil(ordered.size * 0.95).toInt() - 1).coerceAtLeast(0)]
    }

    @Synchronized fun status(): String {
        val p95 = p95Ms()
        return when {
            recovering || consecutiveFailures >= 3 -> "UNRELIABLE"
            consecutiveFailures > 0 -> "DEGRADED"
            samples.size < minSamples -> "UNCALIBRATED"
            p95 != null && p95 > severeP95Ms -> "UNRELIABLE"
            p95 != null && p95 > degradedP95Ms -> "DEGRADED"
            else -> "HEALTHY"
        }
    }

    @Synchronized fun nextIntervalMs(): Long = when (status()) {
        "HEALTHY" -> 500L
        "UNCALIBRATED" -> 1000L
        "DEGRADED" -> 1500L
        else -> 5000L
    }

    @Synchronized fun sampleCount(): Int = samples.size
    fun permitsMoneyActions(): Boolean = false
}
