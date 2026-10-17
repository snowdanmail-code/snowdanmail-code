package com.example.airemote

import android.graphics.Bitmap
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.net.HttpURLConnection
import java.net.URL
import java.io.ByteArrayOutputStream
import java.util.Base64

/** Real Python CV server on the CI host through adb reverse, no GPT or external app. */
@RunWith(AndroidJUnit4::class)
class BackendConnectionTest {
    private fun request(path: String, payload: JSONObject? = null): Pair<Int, JSONObject> {
        val conn = URL("http://127.0.0.1:18787$path").openConnection() as HttpURLConnection
        conn.connectTimeout = 5000; conn.readTimeout = 15000
        conn.setRequestProperty("X-Device-Token", "synthetic-android-cv-test")
        try {
            if (payload != null) {
                conn.requestMethod = "POST"; conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(payload.toString().toByteArray()) }
            }
            val code = conn.responseCode
            val input = if (code in 200..299) conn.inputStream else conn.errorStream
            return code to JSONObject(input.bufferedReader().use { it.readText() })
        } finally { conn.disconnect() }
    }
    @Test fun androidReachesRealBackendAndCvAbstainsOnBlankFrame() {
        val ping = request("/diagnostics/ping")
        assertEquals(200, ping.first); assertEquals("ok", ping.second.getString("status"))
        val bmp = Bitmap.createBitmap(709,1536,Bitmap.Config.ARGB_8888)
        val jpeg = ByteArrayOutputStream().use { bmp.compress(Bitmap.CompressFormat.JPEG,85,it); bmp.recycle(); it.toByteArray() }
        val cards = request("/vision/cards", JSONObject().put("request","vision_cards")
            .put("screen_state","live_table").put("image_base64",Base64.getEncoder().encodeToString(jpeg)))
        assertEquals(200, cards.first)
        assertEquals("offline_glyph_reader", cards.second.getString("mode"))
        assertEquals("abstain", cards.second.getString("quality"))
        assertEquals(0, cards.second.getJSONArray("hero_cards").length())
        assertTrue(cards.second.isNull("action"))
    }
}
