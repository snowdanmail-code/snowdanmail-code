package com.example.airemote

fun main() {
    val w=LatencyWindow(3)
    check(w.count()==0 && w.percentile95()==null)
    w.record(70); w.record(100); w.record(30)
    check(w.percentile95()==100L && w.count()==3)
    w.record(60)
    check(w.count()==3 && w.percentile95()==100L)
    val same=LatencyWindow()
    for(i in 1L..100L) same.record(i)
    check(same.count()==50)
    check(same.percentile95()==98L)
    try {w.record(-1);error("negative") } catch(_: IllegalArgumentException) { }
    try {w.record(120001);error("large") } catch(_: IllegalArgumentException) { }
    println("LATENCY_WINDOW_OK")
}
