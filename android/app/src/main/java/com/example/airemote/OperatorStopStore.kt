package com.example.airemote

import android.content.Context

/** Durable fail-closed operator stop gate shared by Activity, capture and gesture services.
 * A missing preference means STOP. Only an explicit tap on the operator's ARM button permits a session.
 */
object OperatorStopStore {
    private const val PREFS = "operator_control_v1"
    private const val STOPPED = "emergency_stopped"

    fun isStopped(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(STOPPED, true)

    /** commit() is synchronous: do not race an in-flight session against an asynchronous write. */
    fun stop(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(STOPPED, true).commit()

    fun armFromOperator(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(STOPPED, false).commit()
}
