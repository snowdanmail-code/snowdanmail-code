package com.example.airemote

import java.util.concurrent.atomic.AtomicBoolean

/** Operator-owned session permission. STOP always wins until explicit manual re-arm.
 * Not a substitute for the Android service stopping and deleting frame buffers.
 */
class OperatorControl(initiallyStopped: Boolean = false) {
    private val stopped = AtomicBoolean(initiallyStopped)
    fun isStopped(): Boolean = stopped.get()
    fun stop(): Boolean = stopped.compareAndSet(false, true)
    fun resetByOperator() { stopped.set(false) }
    fun mayStart(): Boolean = !stopped.get()
}
