package com.example.airemote

/** Pure-Kotlin Android-side guard between an AI recommendation and any user-approved executor.
 * GPT cannot supply gesture coordinates or force an unsupported state transition.
 */
class PlayChipTurnGuard(private val maxChipsPerAction: Int = 200) {
    data class Turn(
        val handId: String,
        val revision: Long,
        val viewAgeMs: Long,
        val ownTurn: Boolean,
        val twoMatchingFrames: Boolean,
        val playChipsVerified: Boolean,
        val allowedActions: Set<String>,
        val callChips: Int,
        val minRaise: Int,
        val maxRaise: Int,
        val heroStack: Int,
        val modelAuthorized: Boolean
    )
    data class Move(val handId: String, val revision: Long, val action: String, val chips: Int)

    private var stopped = false
    private val used = mutableSetOf<Pair<String, Long>>()

    @Synchronized fun stop() { stopped = true }
    @Synchronized fun isStopped(): Boolean = stopped

    @Synchronized fun authorize(turn: Turn, move: Move): Boolean {
        if (stopped || !turn.playChipsVerified || !turn.modelAuthorized) return false
        if (turn.viewAgeMs !in 0..1500 || !turn.ownTurn || !turn.twoMatchingFrames) return false
        if (turn.handId.isBlank() || move.handId != turn.handId || move.revision != turn.revision) return false
        if ((turn.handId to turn.revision) in used) return false
        if (move.action !in setOf("fold", "check", "call", "bet", "raise")) return false
        if (move.action !in turn.allowedActions || move.chips < 0 || move.chips > maxChipsPerAction || move.chips > turn.heroStack) return false
        when (move.action) {
            "check" -> if (move.chips != 0 || turn.callChips != 0) return false
            "fold" -> if (move.chips != 0) return false
            "call" -> if (turn.callChips <= 0 || move.chips != turn.callChips) return false
            "bet", "raise" -> if (move.chips !in turn.minRaise..turn.maxRaise || move.chips <= 0) return false
        }
        used.add(turn.handId to turn.revision)
        return true
    }
}
