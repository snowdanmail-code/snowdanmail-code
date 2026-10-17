package com.example.airemote

fun main() {
    val noConnection = RttSummary.fromSamples(emptyList(), 6)
    check(noConnection.quality == "NO_CONNECTION" && noConnection.p95Ms == null)
    val healthy = RttSummary.fromSamples(listOf(20, 30, 40, 50, 60, 70), 0)
    check(healthy.successes == 6 && healthy.medianMs == 45L)
    check(healthy.p95Ms == 70L && healthy.quality == "LOW_RTT")
    val moderate = RttSummary.fromSamples(listOf(200, 240, 300), 0)
    check(moderate.quality == "MODERATE_RTT")
    val slow = RttSummary.fromSamples(listOf(800, 1000, 900), 0)
    check(slow.quality == "HIGH_RTT")
    val unstable = RttSummary.fromSamples(listOf(10, 20, 30), 1)
    check(unstable.quality == "UNSTABLE_OR_INSUFFICIENT")
    val few = RttSummary.fromSamples(listOf(10, 20), 0)
    check(few.quality == "UNSTABLE_OR_INSUFFICIENT")
    try { RttSummary.fromSamples(listOf(-1), 0); error("negative RTT accepted") }
    catch (_: IllegalArgumentException) { }
    try { RttSummary.fromSamples(listOf(1), -1); error("negative failures accepted") }
    catch (_: IllegalArgumentException) { }
    println("RttSummary: PASS")
}
