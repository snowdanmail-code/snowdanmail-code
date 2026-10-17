package com.example.airemote

/** Conservative card input transfer; never guesses cards or outs. Pure Kotlin. */
object CardAutoFill {
    data class Cards(val hero: List<String>, val board: List<String>)
    private val card = Regex("^(10|[2-9TJQKA])[CDHS]$", RegexOption.IGNORE_CASE)

    fun checked(quality: String, screenState: String, hero: List<String>, board: List<String>): Cards? {
        if (quality != "complete" || screenState !in setOf("live_table", "showdown")) return null
        if (hero.size != 2 || board.size !in setOf(0, 3, 4, 5)) return null
        val all = hero + board
        if (all.any { !card.matches(it) }) return null
        val normalized = all.map { it.uppercase().replace(Regex("^10"), "T") }
        if (normalized.size != normalized.toSet().size) return null
        fun display(card: String): String = card.dropLast(1) + card.takeLast(1).lowercase()
        return Cards(normalized.take(2).map(::display), normalized.drop(2).map(::display))
    }
}
