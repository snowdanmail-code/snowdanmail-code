package com.example.airemote

import org.junit.Assert.*
import org.junit.Test

/** Runs during :app:testDebugUnitTest in GitHub Actions or Android Studio. */
class OperatorControlJvmTest {
    @Test fun `starts disarmed for safety`() {
        val control = OperatorControl(initiallyStopped = true)
        assertFalse(control.mayStart())
        assertTrue(control.isStopped())
    }

    @Test fun `STOP locks out all future starts until operator re arms`() {
        val control = OperatorControl()
        assertTrue(control.mayStart())
        assertTrue(control.stop())
        assertFalse(control.mayStart())
        assertFalse(control.stop()) // idempotent
        control.resetByOperator()
        assertTrue(control.mayStart())
    }

    @Test fun `repeat STOP remains latched`() {
        val control = OperatorControl()
        repeat(50) { control.stop() }
        assertTrue(control.isStopped())
    }
}
