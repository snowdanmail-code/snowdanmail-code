package com.example.airemote

/** Minimal read-only diagnostics. No frames, cards, names, account data, or tokens. */
data class ObservationEvent(
    val utc: String,
    val sequence: Long,
    val frameAgeMs: Long,
    val rttMs: Long,
    val status: String,
    val cue: String,
    val timeline: String,
) {
    companion object {
        const val TSV_HEADER = "utc\tsequence\tframe_age_ms\trtt_ms\tstatus\tcue\ttimeline"
        private fun safeField(raw: String): String {
            val filtered = raw.filter { !it.isISOControl() && it != '\t' && it != '\r' && it != '\n' }
                .take(64)
            // Prevent spreadsheet formula injection when a report is pasted into a spreadsheet.
            return if (filtered.startsWith('=') || filtered.startsWith('+') ||
                       filtered.startsWith('-') || filtered.startsWith('@')) "'" + filtered
                   else filtered
        }
    }

    fun toTsv(): String = listOf(
        safeField(utc), sequence.toString(), frameAgeMs.coerceAtLeast(0).toString(),
        rttMs.coerceAtLeast(0).toString(), safeField(status), safeField(cue),
        safeField(timeline),
    ).joinToString("\t")
}
