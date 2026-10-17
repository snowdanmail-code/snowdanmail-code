package com.example.airemote

fun main() {
    val a = ObservationEvent("2026-10-17T12:00:00Z", 42, -10, 37, "ok", "=evil\tclick", "unknown\nstatus")
    val line = a.toTsv()
    check(line.split("\t").size == 7) { "Unexpected TSV schema" }
    check(line.contains("\t0\t37\t")) { "Negative ages must clamp to zero" }
    check(line.contains("'=evilclick")) { "Spreadsheet injection not blocked" }
    check(!line.contains('\n') && !line.contains("\t=evil")) { "Unsafe control character" }
    check(ObservationEvent.TSV_HEADER.split("\t").size == 7)
    println("ObservationEventTest PASSED")
}
