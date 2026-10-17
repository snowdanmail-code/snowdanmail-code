package com.example.airemote

import android.content.Context

/** Fast JVM simulation of STOP persistence and manual re-arm across Activity restarts. */
fun main() {
    val savedPrefs = mutableMapOf<String, Boolean>()
    val first = Context(savedPrefs)
    check(OperatorStopStore.isStopped(first)) { "Uninitialized install must be STOPPED" }
    check(OperatorStopStore.armFromOperator(first))
    check(!OperatorStopStore.isStopped(first))
    val restarted = Context(savedPrefs)
    check(!OperatorStopStore.isStopped(restarted)) { "Explicit authorization should survive restart" }
    check(OperatorStopStore.stop(restarted))
    check(OperatorStopStore.isStopped(first)) { "STOP must propagate to other component" }
    check(OperatorStopStore.isStopped(Context(savedPrefs))) { "STOP must survive restart" }
    check(OperatorStopStore.armFromOperator(restarted))
    check(!OperatorStopStore.isStopped(Context(savedPrefs)))
    println("OperatorStopStoreJvmTest: 7 assertions OK (fake Android context)")
}
