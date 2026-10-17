package com.example.airemote

import org.junit.Assert.*
import org.junit.Test

class PlayChipTurnGuardJvmTest {
    private fun turn() = PlayChipTurnGuard.Turn(
        "lab-hand-01", 4L, 120L, true, true, true,
        setOf("fold", "call", "raise"), 20, 60, 120, 150, true)

    @Test fun `accepts first legal play-chip raise`() {
        val guard = PlayChipTurnGuard()
        val action = PlayChipTurnGuard.Move("lab-hand-01", 4L, "raise", 80)
        assertTrue(guard.authorize(turn(), action))
        assertFalse(guard.authorize(turn(), action))
    }

    @Test fun `rejects stale observation`() {
        val guard = PlayChipTurnGuard()
        assertFalse(guard.authorize(turn().copy(viewAgeMs = 2200),
            PlayChipTurnGuard.Move("lab-hand-01", 4L, "raise", 80)))
    }

    @Test fun `rejects any action after STOP`() {
        val guard = PlayChipTurnGuard()
        guard.stop()
        assertFalse(guard.authorize(turn(),
            PlayChipTurnGuard.Move("lab-hand-01", 4L, "fold", 0)))
    }
}
