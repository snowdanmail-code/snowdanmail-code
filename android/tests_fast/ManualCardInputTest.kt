package com.example.airemote

fun main() {
    check(ManualCardInput.tokens("Ah, Kh ; 10s") == listOf("Ah", "Kh", "10s"))
    check(ManualCardInput.tokens("\tAs\n2d  ") == listOf("As", "2d"))
    check(ManualCardInput.tokens("  ").isEmpty())
    try { ManualCardInput.tokens("XX") ; error("bad card accepted") }
    catch (_: IllegalArgumentException) { }
    try { ManualCardInput.tokens("Ah ".repeat(50)) ; error("too many cards accepted") }
    catch (_: IllegalArgumentException) { }
    try { ManualCardInput.tokens("A".repeat(301)) ; error("oversized input accepted") }
    catch (_: IllegalArgumentException) { }
    println("ManualCardInput: PASS")
}
