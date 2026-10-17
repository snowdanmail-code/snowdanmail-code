package com.example.airemote

fun main() {
    val p = ObservationBackoff(windowSize = 8, minSamples = 4)
    check(p.status() == "UNCALIBRATED")
    check(p.nextIntervalMs() == 1000L)
    repeat(4) { p.onSuccess(110) }
    check(p.status() == "HEALTHY")
    check(p.nextIntervalMs() == 500L)
    check(p.p95Ms() == 110L)
    p.onFailure()
    check(p.status() == "DEGRADED" && p.nextIntervalMs() == 1500L)
    p.onFailure()
    p.onFailure()
    check(p.status() == "UNRELIABLE" && p.nextIntervalMs() == 5000L)
    p.onSuccess(200)
    check(p.status() == "UNRELIABLE") // require three successful probes
    p.onSuccess(200)
    check(p.status() == "UNRELIABLE")
    p.onSuccess(200)
    check(p.status() == "HEALTHY")
    p.onNetworkChange("cellular")
    check(p.status() == "UNCALIBRATED" && p.sampleCount() == 0)
    repeat(4) { p.onSuccess(200) }
    check(p.status() == "HEALTHY")
    try { p.onSuccess(-1); error("negative RTT accepted") } catch (_: IllegalArgumentException) {}
    try { p.onNetworkChange("edge"); error("invalid transport accepted") } catch (_: IllegalArgumentException) {}
    check(!p.permitsMoneyActions())
    println("ObservationBackoff: PASS")
}
