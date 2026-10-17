package com.example.airemote

import android.content.Context

/** Explicit-export journal in private app storage, never storing screenshots. */
object ReadOnlySessionJournal {
    private const val NAME = "readonly-observations.tsv"
    private const val MAX_BYTES = 256_000L

    @Synchronized fun append(context: Context, event: ObservationEvent) {
        try {
            val file = context.getFileStreamPath(NAME)
            if (!file.exists() || file.length() >= MAX_BYTES) {
                context.openFileOutput(NAME, Context.MODE_PRIVATE).bufferedWriter().use {
                    it.appendLine(ObservationEvent.TSV_HEADER)
                }
            }
            context.openFileOutput(NAME, Context.MODE_APPEND).bufferedWriter().use {
                it.appendLine(event.toTsv())
            }
        } catch (_: Exception) { /* Diagnostics must never crash screen capture. */ }
    }

    @Synchronized fun read(context: Context): String = try {
        val file = context.getFileStreamPath(NAME)
        if (file.exists()) file.readText(Charsets.UTF_8).takeLast(75_000) else ""
    } catch (_: Exception) { "" }

    @Synchronized fun clear(context: Context) { context.deleteFile(NAME) }
}
