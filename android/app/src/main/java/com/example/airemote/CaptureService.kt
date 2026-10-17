package com.example.airemote

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.*
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.net.HttpURLConnection
import java.net.URL
import java.util.Base64
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/** Foreground-only screen capture with user-visible notification.
 * Streaming means selected JPEG stills, not a 30-fps encoded video. No other-app gestures.
 */
class CaptureService : Service() {
    companion object {
        const val ACTION_START = "com.example.airemote.START_CAPTURE"
        const val ACTION_STOP = "com.example.airemote.STOP_CAPTURE"
        const val ACTION_STREAM_START = "com.example.airemote.START_OBSERVATION"
        const val ACTION_FAST_START = "com.example.airemote.START_FAST_LAB_OBSERVATION"
        const val ACTION_STREAM_STOP = "com.example.airemote.STOP_OBSERVATION"
        const val ACTION_POKER_START = "com.example.airemote.START_POKER"
        const val ACTION_POKER_STOP = "com.example.airemote.STOP_POKER"
        const val EXTRA_POKER_PACKAGE = "expectedAppPackage"
        const val EXTRA_BUTTON_LAYOUT = "buttonLayout"
        const val EXTRA_RESULT_CODE = "resultCode"
        const val EXTRA_DATA = "resultData"
        const val EXTRA_BASE_URL = "baseUrl"
        const val EXTRA_TOKEN = "deviceToken"
    }
    private var projection: MediaProjection? = null
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var worker: HandlerThread? = null
    private var closing = false
    private var lastCaptureCheck = 0L
    private var lastEncodedAt = 0L
    private var lastSignature: ByteArray? = null
    private var lastProfile = -1
    private val streaming = AtomicBoolean(false)
    private var streamGeneration = 0L
    private val pokerRunning = AtomicBoolean(false)
    @Volatile private var pokerGeneration = 0L
    private val callback = object : MediaProjection.Callback() {
        override fun onStop() { stopSelf() }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                OperatorStopStore.stop(this)
                stopStreaming()
                stopPoker()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_STREAM_STOP -> { stopStreaming(); return START_NOT_STICKY }
            ACTION_POKER_STOP -> { stopPoker(); return START_NOT_STICKY }
            ACTION_POKER_START -> {
                if (OperatorStopStore.isStopped(this)) {
                    FrameStore.gameStatus = "Оператор остановил сессию; нужно ручное разрешение"
                    return START_NOT_STICKY
                }
                if (!BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED) {
                    FrameStore.gameStatus = "Лабораторная сборка: внешнее управление отключено"
                    return START_NOT_STICKY
                }
                val base = intent.getStringExtra(EXTRA_BASE_URL) ?: ""
                val token = intent.getStringExtra(EXTRA_TOKEN) ?: ""
                val expected = intent.getStringExtra(EXTRA_POKER_PACKAGE) ?: ""
                val layout = intent.getStringExtra(EXTRA_BUTTON_LAYOUT) ?: ""
                if (projection == null || token.length < 12 ||
                    !expected.matches(Regex("[a-zA-Z0-9_.]{5,120}")) ||
                    expected == packageName) {
                    FrameStore.gameStatus = "Сначала включите захват и введите параметры управления"
                } else startPoker(base,token,expected,layout)
                return START_NOT_STICKY
            }
            ACTION_STREAM_START, ACTION_FAST_START -> {
                if (OperatorStopStore.isStopped(this)) {
                    FrameStore.streamStatus = "Оператор остановил сессию; нужно ручное разрешение"
                    return START_NOT_STICKY
                }
                if (projection == null) {
                    FrameStore.streamStatus = "Разрешите захват экрана перед потоком"
                    return START_NOT_STICKY
                }
                val base = intent.getStringExtra(EXTRA_BASE_URL) ?: ""
                val secret = intent.getStringExtra(EXTRA_TOKEN) ?: ""
                if (base.isEmpty() || secret.length < 12) {
                    FrameStore.streamStatus = "Неверные параметры сервера"
                } else startStreaming(base, secret, fastMode=intent.action == ACTION_FAST_START)
                return START_NOT_STICKY
            }
            ACTION_START -> {
                if (OperatorStopStore.isStopped(this)) {
                    FrameStore.streamStatus = "Оператор остановил сессию; нужно ручное разрешение"
                    return START_NOT_STICKY
                }
                if (projection != null) return START_NOT_STICKY
                startCapture(intent)
                return START_NOT_STICKY
            }
        }
        return START_NOT_STICKY
    }

    private fun startCapture(intent: Intent) {
        try {
            visibleNotification()
            val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
            @Suppress("DEPRECATION")
            val resultData = if (Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(EXTRA_DATA, Intent::class.java)
            } else intent.getParcelableExtra(EXTRA_DATA)
            require(resultCode == Activity.RESULT_OK && resultData != null)
            val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = manager.getMediaProjection(resultCode, resultData)
            requireNotNull(projection)
            projection!!.registerCallback(callback, Handler(Looper.getMainLooper()))
            val metrics = resources.displayMetrics
            val width = metrics.widthPixels
            val height = metrics.heightPixels
            require(width > 0 && height > 0)
            worker = HandlerThread("ScreenSampling").apply { start() }
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
            reader!!.setOnImageAvailableListener({ images ->
                val image = images.acquireLatestImage() ?: return@setOnImageAvailableListener
                try {
                    val now = SystemClock.elapsedRealtime()
                    if (!closing && now - lastCaptureCheck >= 300L) {
                        lastCaptureCheck = now
                        val plane = image.planes[0]
                        val paddedWidth = plane.rowStride / plane.pixelStride
                        val padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888)
                        try {
                            padded.copyPixelsFromBuffer(plane.buffer)
                            val screen = Bitmap.createBitmap(padded, 0, 0, width, height)
                            try {
                                val signature = FrameDifference.signature(screen)
                                val profile = CaptureOptions.profile.coerceIn(0, 3)
                                val mustRefresh = (now - lastEncodedAt >= 8000L) || profile != lastProfile
                                if (mustRefresh || FrameDifference.changed(lastSignature, signature)) {
                                    // At most ~2 JPEG encodes/s; uploader has its own slower pacing.
                                    val target = CaptureOptions.longEdges[profile]
                                    val scale = minOf(1.0, target.toDouble() / maxOf(width, height))
                                    val w = maxOf(1, (width * scale).toInt())
                                    val h = maxOf(1, (height * scale).toInt())
                                    val smaller = Bitmap.createScaledBitmap(screen, w, h, true)
                                    try {
                                        val jpeg = ByteArrayOutputStream().use { output ->
                                            smaller.compress(Bitmap.CompressFormat.JPEG,
                                                CaptureOptions.qualities[profile], output)
                                            output.toByteArray()
                                        }
                                        // Reject oversized frames rather than bypass backend limits.
                                        if (jpeg.size <= 650_000) {
                                            val seq = FrameStore.frameSequence + 1L
                                            FrameStore.latest = FrameInfo(jpeg, seq, w, h,
                                                CaptureOptions.qualities[profile], profile, now)
                                            FrameStore.frameSequence = seq
                                            lastEncodedAt = now
                                            lastSignature = signature
                                            lastProfile = profile
                                        } else FrameStore.captureError = "Кадр слишком большой — выберите меньший профиль"
                                    } finally { if (smaller !== screen) smaller.recycle() }
                                }
                            } finally { screen.recycle() }
                        } finally { padded.recycle() }
                    }
                } catch (e: Exception) {
                    FrameStore.captureError = "Ошибка захвата: ${e.message}"
                } finally { image.close() }
            }, Handler(worker!!.looper))
            display = projection!!.createVirtualDisplay("AI Remote Control", width, height,
                metrics.densityDpi, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader!!.surface, null, Handler(worker!!.looper))
            FrameStore.isCapturing = true
            FrameStore.captureError = ""
        } catch (e: Exception) {
            FrameStore.captureError = e.message ?: "Ошибка при запуске MediaProjection"
            stopSelf()
        }
    }

    private fun startStreaming(base: String, token: String, fastMode: Boolean = false) {
        if (streaming.get()) return
        streaming.set(true)
        // The old <=1280px presets cannot reliably read small 1win cards.
        if (fastMode) CaptureOptions.profile = 3
        FrameStore.isStreaming = true
        FrameStore.streamStatus = if (fastMode) "Быстрый локальный тест (без GPT/ставок)" else "Поток наблюдения запущен"
        val generation = ++streamGeneration
        val sessionId = UUID.randomUUID().toString()
        val latencyWindow = LatencyWindow()
        val e2eTraceWindow = ClientTraceWindow()
        val observationBackoff = ObservationBackoff()
        thread(name = "OptInFrameUploader", isDaemon = true) {
            var lastSequence = -1L
            var lastSentAt = 0L
            var uploads = 0
            // Long enough for a genuine phone UI observation session; still bounded.
            val maxUploads = if (fastMode) 1200 else 100
            // No unbounded queue: while HTTP is in-flight, newest frame replaces older ones.
            while (streaming.get() && !closing && generation == streamGeneration && uploads < maxUploads) {
                try {
                    Thread.sleep(if (fastMode) observationBackoff.nextIntervalMs() else 400)
                    val frame = FrameStore.latest ?: continue
                    val now = SystemClock.elapsedRealtime()
                    if (!FastCapturePolicy.shouldUpload(frame.seq, lastSequence,
                            frame.capturedAtMs, now, lastSentAt, fastMode)) continue
                    // Service can observe other apps only with explicit MediaProjection consent.
                    lastSentAt = now
                    lastSequence = frame.seq
                    uploads++
                    e2eTraceWindow.onFrame(frame.seq)
                    val body = JSONObject().apply {
                        put("request", if (fastMode) "fast_observe" else "stream_observe")
                        put("session_id", sessionId)
                        put("sequence", frame.seq)
                        put("image_base64", Base64.getEncoder().encodeToString(frame.jpeg))
                        if (fastMode) {
                            put("frame_age_ms", (now - frame.capturedAtMs).coerceAtLeast(0L))
                            // No OCR-based timer available yet. Null is explicit and fail-closed.
                            put("remaining_ms", JSONObject.NULL)
                            put("screen_state", "unknown")
                        } else put("frame", JSONObject().apply {
                            put("width", frame.width)
                            put("height", frame.height)
                            put("jpeg_quality", frame.quality)
                            put("profile", frame.profile)
                        })
                    }
                    val connection = (URL("$base/${if (fastMode) "fast/observe" else "stream/observe"}").openConnection() as HttpURLConnection).apply {
                        requestMethod = "POST"
                        setRequestProperty("X-Device-Token", token)
                        setRequestProperty("Content-Type", "application/json")
                        connectTimeout = if (fastMode) 1000 else 7000
                        readTimeout = if (fastMode) 1800 else 45000
                        doOutput = true
                    }
                    val requestStartedAt = SystemClock.elapsedRealtime()
                    val result = try {
                        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                        val status = connection.responseCode
                        val responseStream = if (status in 200..299) connection.inputStream else connection.errorStream
                        val response = responseStream?.bufferedReader()?.use { it.readText() } ?: "{}"
                        if (status !in 200..299) throw IllegalStateException("HTTP $status")
                        JSONObject(response)
                    } finally { connection.disconnect() }
                    val rttMs = (SystemClock.elapsedRealtime() - requestStartedAt).coerceAtLeast(0L)
                    latencyWindow.record(rttMs)
                    if (fastMode) observationBackoff.onSuccess(rttMs)
                    // A newer frame may have arrived while HTTP was in-flight.
                    e2eTraceWindow.onFrame(FrameStore.frameSequence)
                    val captureToResponseMs = e2eTraceWindow.onResponse(
                        frame.seq, frame.capturedAtMs, SystemClock.elapsedRealtime())
                    if (!streaming.get() || closing || generation != streamGeneration) break
                    if (fastMode) {
                        val latency = result.optDouble("processing_ms",-1.0)
                        val cues = result.optJSONObject("turn_cues")
                        val timeline = result.optJSONObject("turn_timeline")
                        val uiHint = cues?.optString("cue", "кадр не классифицирован") ?: "ожидание следующего кадра"
                        val hold = timeline?.optString("status", "не подтверждено") ?: "нет устойчивого сигнала"
                        ReadOnlySessionJournal.append(applicationContext,
                            ObservationEvent(Instant.now().toString(), frame.seq,
                                (now - frame.capturedAtMs).coerceAtLeast(0L), rttMs,
                                result.optString("status", "unknown"), uiHint, hold))
                        FrameStore.streamStatus = "v2.7 read-only: ${result.optString("status")}; $uiHint; $hold; CPU ${latency} мс; " +
                            "RTT ${rttMs} мс; p95 RTT ${latencyWindow.percentile95()} мс; " +
                            "сеть ${observationBackoff.status()} (интервал ${observationBackoff.nextIntervalMs()} мс); " +
                            "capture→reply p95 ${e2eTraceWindow.p95Ms()} мс; " +
                            "$captureToResponseMs. Таймер не проверен; ставки выключены"
                        continue
                    }
                    val readability = result.optString("readability")
                    if (readability == "unclear" && CaptureOptions.profile < 3) {
                        CaptureOptions.profile += 1 // escalates fidelity, NEVER downscales automatically
                    }
                    FrameStore.streamStatus = "${result.optString("mode")}: " +
                        result.optString("summary", result.optString("status", "кадр принят")).take(170)
                } catch (e: InterruptedException) { break }
                catch (e: Exception) {
                    if (fastMode) observationBackoff.onFailure()
                    FrameStore.streamStatus = "Ошибка наблюдения: ${e.message}; сеть ${observationBackoff.status()}"
                    try { Thread.sleep(if (fastMode) 100L else 1500L) } catch (_: InterruptedException) { break }
                }
            }
            if (generation == streamGeneration) {
                streaming.set(false)
                FrameStore.isStreaming = false
                if (uploads >= maxUploads) FrameStore.streamStatus = "Лимит $maxUploads кадров — запустите новую сессию вручную"
            }
        }
    }

    /** Configured UI click coordinates stay on the phone, never originate from GPT. */
    private fun parseButtons(raw: String): Map<String, Pair<Float, Float>> {
        val json = JSONObject(raw)
        val parsed = mutableMapOf<String, Pair<Float,Float>>()
        for (name in listOf("fold", "check", "call", "raise")) {
            if (!json.has(name)) continue
            val coords = json.getJSONArray(name)
            require(coords.length() == 2) { "Expected [x,y] for $name" }
            val x = coords.getDouble(0).toFloat()
            val y = coords.getDouble(1).toFloat()
            require(x in 0.02f..0.98f && y in 0.02f..0.98f) { "Invalid target $name" }
            parsed[name] = Pair(x,y)
        }
        require(parsed.isNotEmpty()) { "No configured buttons" }
        return parsed.toMap()
    }

    private fun startPoker(base: String,token: String,expected: String, rawButtons: String) {
        if (!BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED) {
            FrameStore.gameStatus = "Внешние действия отключены"
            return
        }
        if (pokerRunning.get()) return
        val buttons=try { parseButtons(rawButtons) } catch(e: Exception) {
            FrameStore.gameStatus="Калибровка кнопок не задана: ${e.message}"
            return
        }
        // No source-code default click locations, no actions outside calibrated positions.
        if (!DemoAccessibilityService.enabled()) {
            FrameStore.gameStatus="Включите службу специальных возможностей"; return
        }
        pokerRunning.set(true)
        FrameStore.isGameRunning=true
        FrameStore.gameStatus="Режим запущен: ожидается окно $expected"
        val epoch=++pokerGeneration
        val session=UUID.randomUUID().toString()
        thread(name="ExplicitPokerSession",isDaemon=true) {
            var seq=-1L
            var issued=0
            var requests=0
            try {
                while (pokerRunning.get() && !closing && epoch==pokerGeneration && requests<30 && issued<20) {
                    Thread.sleep(1000) // stability pacing; NOT imitation of a human
                    if (!DemoAccessibilityService.isExpectedApp(expected)) continue
                    val frame=FrameStore.latest ?: continue
                    if (frame.seq<=seq) continue
                    // Never ask GPT to decide from an already outdated screenshot.
                    if (SystemClock.elapsedRealtime() - frame.capturedAtMs !in 0L..1200L) continue
                    seq=frame.seq
                    requests++
                    val body=JSONObject().apply {
                        put("request","poker_decide")
                        put("session_id",session)
                        put("sequence",frame.seq)
                        put("image_base64",Base64.getEncoder().encodeToString(frame.jpeg))
                    }
                    val connection=(URL("$base/poker/decide").openConnection() as HttpURLConnection).apply {
                        requestMethod="POST";doOutput=true
                        setRequestProperty("Content-Type","application/json")
                        setRequestProperty("X-Device-Token",token)
                        connectTimeout=1500;readTimeout=4500
                    }
                    val result=try {
                        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                        val status=connection.responseCode
                        val input=if(status in 200..299) connection.inputStream else connection.errorStream
                        val json=input?.bufferedReader()?.use { it.readText() } ?: "{}"
                        if(status !in 200..299) throw IllegalStateException("HTTP $status $json")
                        JSONObject(json)
                    } finally { connection.disconnect() }
                    if (!pokerRunning.get() || closing || epoch!=pokerGeneration) break
                    val command=result.optString("action","wait")
                    // Model latency is unbounded. A response is NOT valid simply because
                    // screenshot sequence did not change while the screen was static.
                    if (SystemClock.elapsedRealtime() - frame.capturedAtMs > 1800L) {
                        FrameStore.gameStatus="Ответ GPT опоздал — действие отменено"
                        continue
                    }
                    FrameStore.gameStatus="GPT: $command; ${result.optString("reason").take(100)}"
                    if (!result.optBoolean("enabled",false) || command=="wait") continue
                    if (result.optString("scope")!="configured_package_only" ||
                         result.optLong("sequence",-1L)!=frame.seq)
                        throw IllegalStateException("Ответ не соответствует кадру или политике")
                    val coord=buttons[command] ?: throw IllegalStateException("Нет калибровки '$command'")
                    // A model decision that is stale is discarded, never clicked.
                    if (FrameStore.frameSequence != frame.seq)
                        throw IllegalStateException("Изменился экран до нажатия")
                    if (!DemoAccessibilityService.isExpectedApp(expected))
                        throw IllegalStateException("Изменилось активное приложение")
                    val sent=DemoAccessibilityService.tapConfiguredWindowBlocking(expected,coord.first,coord.second)
                    if (!sent) throw IllegalStateException("Нажатие не подтверждено Android")
                    issued++
                    val deadline=SystemClock.elapsedRealtime()+3500L
                    while (pokerRunning.get() && epoch==pokerGeneration &&
                         FrameStore.frameSequence<=frame.seq && SystemClock.elapsedRealtime()<deadline)
                         Thread.sleep(150)
                    if (FrameStore.frameSequence<=frame.seq)
                        throw IllegalStateException("Нет нового кадра после жеста")
                    // Changed screen does not necessarily prove that a monetary wager was accepted.
                    FrameStore.gameStatus="Выполнено жестов: $issued; команда: $command. Фактическая ставка не подтверждена"
                }
                if (requests>=30 || issued>=20) FrameStore.gameStatus="Лимит сессии — остановлено"
            } catch(e: Exception) {
                FrameStore.gameStatus="ОСТАНОВЛЕНО: ${e.message}"
            } finally {
                if (epoch==pokerGeneration) {
                    pokerRunning.set(false)
                    FrameStore.isGameRunning=false
                }
            }
        }
    }

    private fun stopPoker() {
        pokerGeneration++
        pokerRunning.set(false)
        FrameStore.isGameRunning=false
        FrameStore.gameStatus="Игровой агент остановлен оператором"
    }

    private fun stopStreaming() {
        streamGeneration++
        streaming.set(false)
        FrameStore.isStreaming = false
        FrameStore.streamStatus = "Поток остановлен пользователем"
    }

    private fun visibleNotification() {
        val id = "capture_visible"
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(id, "Захват экрана", NotificationManager.IMPORTANCE_LOW))
        val intent = Intent(this, CaptureService::class.java).setAction(ACTION_STOP)
        val pending = PendingIntent.getService(this, 5, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(this, id)
            .setContentTitle("AI Remote Control — захват экрана включён")
            .setContentText("Разрешённый сеанс. Нажмите STOP, чтобы удалить кадры")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_delete, "СТОП ЗАХВАТ", pending)
            .build()
        if (Build.VERSION.SDK_INT >= 29)
            startForeground(11, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        else startForeground(11, notification)
    }

    override fun onDestroy() {
        closing = true
        stopStreaming()
        stopPoker()
        try { display?.release() } catch (_: Exception) {}
        try { reader?.close() } catch (_: Exception) {}
        try { projection?.unregisterCallback(callback) } catch (_: Exception) {}
        try { projection?.stop() } catch (_: Exception) {}
        worker?.quitSafely()
        FrameStore.clear()
        super.onDestroy()
    }
}
