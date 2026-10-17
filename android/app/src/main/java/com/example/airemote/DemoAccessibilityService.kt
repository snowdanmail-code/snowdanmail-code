package com.example.airemote

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** One allowlisted target INSIDE our own app. No arbitrary taps or coordinates. */
class DemoAccessibilityService : AccessibilityService() {
    companion object {
        @Volatile private var active: DemoAccessibilityService? = null
        fun enabled(): Boolean = active != null
        fun isExpectedApp(expectedPackage: String): Boolean =
            active?.rootInActiveWindow?.packageName?.toString() == expectedPackage
        fun isOwnAppActive(): Boolean {
            val service = active ?: return false
            return service.rootInActiveWindow?.packageName?.toString() == service.packageName
        }
        fun tapOwnDemoButton(): Boolean = active?.tapOwnButton() ?: false

        /** For the test loop only; must be called off the UI thread. */
        fun tapOwnDemoButtonBlocking(timeoutMs: Long = 3500): Boolean {
            val service = active ?: return false
            if (OperatorStopStore.isStopped(service)) return false
            val latch = CountDownLatch(1)
            val result = AtomicBoolean(false)
            Handler(Looper.getMainLooper()).post {
                if (OperatorStopStore.isStopped(service)) {
                    latch.countDown()
                    return@post
                }
                val queued = service.tapOwnButton { success ->
                    result.set(success)
                    latch.countDown()
                }
                if (!queued) latch.countDown()
            }
            return latch.await(timeoutMs, TimeUnit.MILLISECONDS) && result.get()
        }
        /** Explicitly targeted window only: never allow the model to supply tap coordinates. */
        fun tapConfiguredWindowBlocking(expectedPackage: String, x: Float, y: Float, timeoutMs: Long = 3200): Boolean {
            // Third defense-in-depth guard: never tap another app in the read-only lab build.
            if (!BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED) return false
            if (expectedPackage.length !in 5..120 ||
                !expectedPackage.matches(Regex("[a-zA-Z0-9_.]+")) ||
                expectedPackage == "com.example.airemote" ||
                x !in 0.02f..0.98f || y !in 0.02f..0.98f) return false
            val service = active ?: return false
            if (OperatorStopStore.isStopped(service)) return false
            val latch = CountDownLatch(1)
            val successful = AtomicBoolean(false)
            Handler(Looper.getMainLooper()).post {
                if (OperatorStopStore.isStopped(service)) {
                    latch.countDown()
                    return@post
                }
                val root = service.rootInActiveWindow
                if (root?.packageName?.toString() != expectedPackage) {
                    latch.countDown()
                    return@post
                }
                val bounds = Rect()
                root.getBoundsInScreen(bounds)
                if (bounds.width() < 100 || bounds.height() < 100) {
                    latch.countDown()
                    return@post
                }
                // Coordinates are a USER-configured fraction of the current active app window.
                val px = bounds.left + x * bounds.width()
                val py = bounds.top + y * bounds.height()
                val path = Path().apply { moveTo(px, py) }
                val gesture = GestureDescription.Builder().addStroke(
                    GestureDescription.StrokeDescription(path, 0, 90)).build()
                val queued = service.dispatchGesture(gesture, object : GestureResultCallback() {
                    override fun onCompleted(gestureDescription: GestureDescription?) {
                        successful.set(true); latch.countDown()
                    }
                    override fun onCancelled(gestureDescription: GestureDescription?) {
                        latch.countDown()
                    }
                }, Handler(Looper.getMainLooper()))
                if (!queued) latch.countDown()
            }
            return latch.await(timeoutMs, TimeUnit.MILLISECONDS) && successful.get()
        }
    }

    override fun onServiceConnected() { super.onServiceConnected(); active = this }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit
    override fun onDestroy() { if (active === this) active = null; super.onDestroy() }

    private fun tapOwnButton(onResult: ((Boolean) -> Unit)? = null): Boolean {
        if (OperatorStopStore.isStopped(this)) return false
        val root = rootInActiveWindow ?: return false
        if (root.packageName?.toString() != packageName) return false
        val nodes = root.findAccessibilityNodeInfosByViewId("$packageName:id/testTarget")
        val node = nodes.firstOrNull() ?: return false
        if (!node.isVisibleToUser || !node.isEnabled) return false
        val bounds = Rect()
        node.getBoundsInScreen(bounds)
        if (bounds.isEmpty) return false
        val path = Path().apply { moveTo(bounds.exactCenterX(), bounds.exactCenterY()) }
        val gesture = GestureDescription.Builder().addStroke(
            GestureDescription.StrokeDescription(path, 0, 90)).build()
        return dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) { onResult?.invoke(true) }
            override fun onCancelled(gestureDescription: GestureDescription?) { onResult?.invoke(false) }
        }, Handler(Looper.getMainLooper()))
    }
}
