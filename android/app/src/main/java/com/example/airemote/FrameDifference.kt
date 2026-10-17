package com.example.airemote

import android.graphics.Bitmap
import kotlin.math.abs

/** Small coarse signature used only for event selection, never for OCR or decisions. */
object FrameDifference {
    fun signature(source: Bitmap): ByteArray {
        val small = Bitmap.createScaledBitmap(source, 48, 96, true)
        val pixels = IntArray(48 * 96)
        small.getPixels(pixels, 0, 48, 0, 0, 48, 96)
        if (small !== source) small.recycle()
        return ByteArray(pixels.size) { i ->
            val rgb = pixels[i]
            (((rgb shr 16 and 255) * 3 + (rgb shr 8 and 255) * 6 + (rgb and 255)) / 10).toByte()
        }
    }

    fun changed(previous: ByteArray?, current: ByteArray): Boolean {
        if (previous == null || previous.size != current.size) return true
        var changedPixels = 0
        for (i in current.indices) {
            if (abs((previous[i].toInt() and 255) - (current[i].toInt() and 255)) >= 14) changedPixels++
        }
        return changedPixels >= maxOf(4, current.size / 1250) // ~0.09% grid
    }
}
