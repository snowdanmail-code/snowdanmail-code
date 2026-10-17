package com.example.airemote

fun main() {
    val client = ClientTraceWindow(capacity=3, maxFrameAgeMs=1300)
    check(client.count() == 0 && client.p95Ms() == null)
    client.onFrame(1)
    check(client.onResponse(1, 1000, 1200) == "FRESH_OBSERVATION_ONLY")
    client.onFrame(3)
    check(client.onResponse(2, 1500, 1600) == "SUPERSEDED")
    check(client.onResponse(3, 1000, 2500) == "STALE_RESPONSE")
    check(client.count() == 3 && client.p95Ms() == 1500L)
    check(client.onResponse(3, 3000, 2500) == "CLOCK_REGRESSION")
    check(client.p95Ms() == 1500L)
    check(!client.grantsMoneyActions())
    try { client.onFrame(-1); error("should reject") } catch (_: IllegalArgumentException) { }
    try { client.onResponse(4, -1, 1); error("should reject") } catch (_: IllegalArgumentException) { }
    val rolling = ClientTraceWindow(capacity=2)
    rolling.onFrame(10)
    rolling.onResponse(10, 100, 250)
    rolling.onResponse(10, 200, 400)
    rolling.onResponse(10, 300, 600)
    check(rolling.count() == 2 && rolling.p95Ms() == 300L)
    println("CLIENT_TRACE_WINDOW_OK")
}
