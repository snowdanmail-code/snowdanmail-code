package com.example.airemote

/** Latest-only buffer: never keep a queue of stale screenshots in RAM. */
data class FrameInfo(val jpeg: ByteArray, val seq: Long, val width: Int,
                     val height: Int, val quality: Int, val profile: Int,
                     val capturedAtMs: Long)

object CaptureOptions {
    /** 0-2 general visual monitoring, 3 full-resolution lab card/money reader. */
    @Volatile var profile: Int = 1
    val longEdges = intArrayOf(720, 960, 1280, 1536)
    val qualities = intArrayOf(55, 75, 88, 75)
}

object FrameStore {
    @Volatile var latest: FrameInfo? = null
    val latestJpeg: ByteArray? get() = latest?.jpeg
    @Volatile var isCapturing: Boolean = false
    @Volatile var frameSequence: Long = 0
    @Volatile var captureError: String = ""
    @Volatile var streamStatus: String = "Поток выключен"
    @Volatile var isStreaming: Boolean = false
    @Volatile var gameStatus: String = "Игровой агент остановлен"
    @Volatile var isGameRunning: Boolean = false
    fun clear() {
        latest = null
        isCapturing = false
        isStreaming = false
        isGameRunning = false
        gameStatus = "Игровой агент остановлен"
        streamStatus = "Поток выключен"
    }
}
