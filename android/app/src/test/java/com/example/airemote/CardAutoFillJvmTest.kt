package com.example.airemote
import org.junit.Assert.*
import org.junit.Test
class CardAutoFillJvmTest {
    @Test fun completeFlopNormalizesCards() {
        val cards = CardAutoFill.checked("complete", "live_table", listOf("10H", "ac"), listOf("2d", "3s", "4h"))!!
        assertEquals(listOf("Th", "Ac"), cards.hero)
    }
    @Test fun unknownOrPartialCannotFill() {
        assertNull(CardAutoFill.checked("abstain", "live_table", listOf("Ah", "Kh"), emptyList()))
        assertNull(CardAutoFill.checked("complete", "unknown", listOf("Ah", "Kh"), emptyList()))
        assertNull(CardAutoFill.checked("complete", "live_table", listOf("Ah", "Kh"), listOf("2c")))
    }
    @Test fun duplicatesAndInvalidCardsCannotFill() {
        assertNull(CardAutoFill.checked("complete", "live_table", listOf("Ah", "ah"), emptyList()))
        assertNull(CardAutoFill.checked("complete", "live_table", listOf("1h", "Kh"), emptyList()))
    }
}
