import com.example.airemote.PlayChipTurnGuard

fun main() {
    fun turn() = PlayChipTurnGuard.Turn("h1", 7, 300L, true, true, true,
        setOf("fold", "call", "raise"), 25, 75, 160, 500, true)
    fun raise(amount: Int) = PlayChipTurnGuard.Move("h1", 7, "raise", amount)
    val checker = PlayChipTurnGuard(200)
    check(checker.authorize(turn(), raise(100)))
    check(!checker.authorize(turn(), raise(100)))
    check(!PlayChipTurnGuard().authorize(turn().copy(playChipsVerified=false),raise(100)))
    check(!PlayChipTurnGuard().authorize(turn().copy(modelAuthorized=false),raise(100)))
    check(!PlayChipTurnGuard().authorize(turn().copy(viewAgeMs=1900L),raise(100)))
    check(!PlayChipTurnGuard().authorize(turn().copy(twoMatchingFrames=false),raise(100)))
    check(!PlayChipTurnGuard().authorize(turn(),raise(70)))
    check(!PlayChipTurnGuard().authorize(turn(),raise(201)))
    check(!PlayChipTurnGuard().authorize(turn(),PlayChipTurnGuard.Move("h1",7,"call",24)))
    check(!PlayChipTurnGuard().authorize(turn(),PlayChipTurnGuard.Move("h1",7,"check",0)))
    check(!PlayChipTurnGuard().authorize(turn(),PlayChipTurnGuard.Move("h1",8,"call",25)))
    val stop = PlayChipTurnGuard();stop.stop()
    check(!stop.authorize(turn(),raise(100)))
    println("PLAY_CHIP_TURN_GUARD: 12 scenarios passed")
}
