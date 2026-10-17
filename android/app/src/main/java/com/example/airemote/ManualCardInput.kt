package com.example.airemote

/** Pure Kotlin manual card-entry validator, never reads other apps or performs gestures. */
object ManualCardInput {
    private val card = Regex("^(10|[2-9TJQKA])[CDHS]$", RegexOption.IGNORE_CASE)

    fun tokens(raw: String): List<String> {
        require(raw.length <= 300) { "Слишком длинный ввод карт" }
        if (raw.isBlank()) return emptyList()
        val values = raw.trim().split(Regex("[,;\\s]+"))
        require(values.size <= 47) { "Слишком много карт" }
        require(values.all { card.matches(it) }) { "Некорректная запись карты" }
        return values
    }
}
