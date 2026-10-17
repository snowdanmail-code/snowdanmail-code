package com.example.airemote

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.SystemClock
import android.view.WindowInsets
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiSelector
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

@RunWith(AndroidJUnit4::class)
class DeviceSmokeTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun blankJpeg(): ByteArray {
        val bitmap = Bitmap.createBitmap(709, 1536, Bitmap.Config.ARGB_8888)
        return ByteArrayOutputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, out); bitmap.recycle(); out.toByteArray()
        }
    }
    private fun frame() {
        FrameStore.latest = FrameInfo(blankJpeg(), 100, 709, 1536, 85, 3, SystemClock.elapsedRealtime())
        FrameStore.isCapturing = true
    }
    @Test fun launchInsetsAndPersistentStop() {
        OperatorStopStore.stop(context)
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val stop = activity.findViewById<Button>(R.id.emergencyStop)
                val loc = IntArray(2); stop.getLocationOnScreen(loc)
                val safe = activity.window.decorView.rootWindowInsets.getInsets(
                    WindowInsets.Type.statusBars() or WindowInsets.Type.displayCutout())
                assertTrue("STOP overlaps status bar: ${loc[1]} < ${safe.top}", loc[1] >= safe.top)
                assertTrue(OperatorStopStore.isStopped(activity))
                activity.findViewById<Button>(R.id.armSession).performClick()
                assertFalse(OperatorStopStore.isStopped(activity))
                stop.performClick()
                assertTrue(OperatorStopStore.isStopped(activity))
                assertNull(FrameStore.latest)
            }
            scenario.recreate()
            scenario.onActivity { assertTrue(OperatorStopStore.isStopped(it)) }
        }
    }
    @Test fun cardResponseFillsFieldsAndClearsOldOuts() {
        val ready = CountDownLatch(1)
        ServerSocket(8787, 1, java.net.InetAddress.getByName("127.0.0.1")).use { socket ->
            val worker = thread {
                socket.accept().use { client ->
                    client.soTimeout = 5000
                    val input = client.getInputStream().bufferedReader()
                    var size = 0
                    while (true) {
                        val line = input.readLine() ?: break
                        if (line.startsWith("Content-Length:", true)) size = line.substringAfter(':').trim().toInt()
                        if (line.isEmpty()) break
                    }
                    repeat(size) { input.read() }
                    val body = """{"quality":"complete","screen_state":"live_table","hero_cards":["Ah","Kd"],"board_cards":["2c","3d","4s"]}""".toByteArray()
                    client.getOutputStream().apply {
                        write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray())
                        write(body); flush()
                    }
                    ready.countDown()
                }
            }
            OperatorStopStore.armFromOperator(context)
            ActivityScenario.launch(MainActivity::class.java).use { scenario ->
                scenario.onActivity {
                    it.findViewById<EditText>(R.id.deviceToken).setText("synthetic-device-test")
                    it.findViewById<EditText>(R.id.backendUrl).setText("http://127.0.0.1:8787")
                    it.findViewById<EditText>(R.id.outCards).setText("Qh")
                    frame()
                    it.findViewById<Button>(R.id.recognizeCards).performClick()
                }
                assertTrue("HTTP response timed out", ready.await(15, TimeUnit.SECONDS))
                SystemClock.sleep(500)
                scenario.onActivity {
                    assertEquals("Ah Kd", it.findViewById<EditText>(R.id.heroCards).text.toString())
                    assertEquals("2c 3d 4s", it.findViewById<EditText>(R.id.boardCards).text.toString())
                    assertEquals("", it.findViewById<EditText>(R.id.outCards).text.toString())
                }
            }
            worker.join(2000)
        }
        FrameStore.clear(); OperatorStopStore.stop(context)
    }
    @Test fun mediaProjectionProducesFrameAndStopClearsIt() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val device = UiDevice.getInstance(inst)
        device.executeShellCommand("pm grant ${context.packageName} android.permission.POST_NOTIFICATIONS")
        OperatorStopStore.armFromOperator(context)
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val method = MainActivity::class.java.getDeclaredMethod("showCaptureDialog")
                method.isAccessible = true; method.invoke(activity)
            }
            SystemClock.sleep(1500)
            val single = device.findObject(UiSelector().textContains("A single app"))
            if (single.exists()) {
                single.click(); SystemClock.sleep(400)
                device.findObject(UiSelector().textContains("Entire screen")).click()
            }
            val entire = device.findObject(UiSelector().textContains("Entire screen"))
            val start = device.findObject(UiSelector().textMatches("(?i)(start now|start|share screen)"))
            assertTrue("Screen capture consent missing", start.waitForExists(5000))
            start.click()
            val deadline = SystemClock.elapsedRealtime() + 15000
            while (FrameStore.latest == null && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(200)
            assertNotNull("No MediaProjection JPEG: ${FrameStore.captureError}", FrameStore.latest)
            assertTrue(FrameStore.latest!!.jpeg.size > 200)
            scenario.onActivity { it.findViewById<Button>(R.id.emergencyStop).performClick() }
            SystemClock.sleep(500)
            assertTrue(OperatorStopStore.isStopped(context))
            assertNull(FrameStore.latest)
            assertFalse(FrameStore.isCapturing)
        }
    }
}
