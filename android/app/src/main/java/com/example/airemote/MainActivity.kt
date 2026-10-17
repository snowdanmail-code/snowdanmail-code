package com.example.airemote

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.*
import org.json.JSONObject
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.Base64
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** User-led screenshot + autonomous one-tap cycle confined to this demo app. */
class MainActivity : Activity() {
    private var playChipTurnGuard = PlayChipTurnGuard()
    private val operatorControl by lazy { OperatorControl(initiallyStopped = OperatorStopStore.isStopped(this)) }
    private val projectionRequest = 501
    private val notificationRequest = 502
    private lateinit var status: TextView
    private lateinit var aiResult: TextView
    private lateinit var preview: ImageView
    private lateinit var backend: EditText
    private lateinit var heroCardsInput: EditText
    private lateinit var boardCardsInput: EditText
    private lateinit var outCardsInput: EditText
    private lateinit var deviceToken: EditText
    private lateinit var testTarget: Button
    private lateinit var expectedGameApp: EditText
    private lateinit var calibratedButtons: EditText
    @Volatile private var tapCount = 0
    private var readOnlyStartPending = false
    private val uiHandler = Handler(Looper.getMainLooper())
    private val recognitionGeneration = AtomicInteger(0)
    private val recognitionBusy = AtomicBoolean(false)
    private val agentRunning = AtomicBoolean(false)
    private val cycleVersion = AtomicInteger(0)
    @Volatile private var appForeground = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 28, 24, 30)
        }
        // Persistent emergency controls OUTSIDE the scrolling settings/form.
        val root = LinearLayout(this).apply {
            id = R.id.safeRoot
            orientation = LinearLayout.VERTICAL
            setOnApplyWindowInsetsListener { view, insets ->
                if (Build.VERSION.SDK_INT >= 30) {
                    val safe = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                    view.setPadding(safe.left, safe.top, safe.right, safe.bottom)
                } else {
                    @Suppress("DEPRECATION")
                    view.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                        insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
                }
                insets
            }
        }
        val stop = Button(this).apply {
            id = R.id.emergencyStop
            text = "СТОП — ПРЕКРАТИТЬ ВСЕ ДЕЙСТВИЯ"
            textSize = 18f
            setBackgroundColor(android.graphics.Color.rgb(160, 25, 25))
            setTextColor(android.graphics.Color.WHITE)
            setOnClickListener { emergencyStop() }
        }
        root.addView(stop, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        val arm = Button(this).apply {
            id = R.id.armSession
            text = "РАЗРЕШИТЬ НОВУЮ ТЕСТОВУЮ СЕССИЮ"
            setOnClickListener {
                if (!OperatorStopStore.armFromOperator(this@MainActivity)) {
                    Toast.makeText(this@MainActivity, "Не удалось сохранить разрешение. Сессия заблокирована.", Toast.LENGTH_LONG).show()
                    return@setOnClickListener
                }
                playChipTurnGuard = PlayChipTurnGuard()
                operatorControl.resetByOperator()
                Toast.makeText(this@MainActivity, "Разрешена новая сессия. Ничего не запущено.", Toast.LENGTH_SHORT).show()
            }
        }
        root.addView(arm, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        val scroller = ScrollView(this).apply { addView(layout) }
        root.addView(scroller, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)
        root.requestApplyInsets()
        fun headline(value: String) = TextView(this).apply {
            text = value
            textSize = 20f
            setPadding(0, 8, 0, 14)
            layout.addView(this)
        }
        fun button(value: String, action: () -> Unit) = Button(this).apply {
            text = value
            setOnClickListener { action() }
            layout.addView(this)
        }
        headline("AI Remote Control v2.12 — ИИ-игрок: проверка APK")
        layout.addView(TextView(this).apply {
            text = "Цель: ИИ-игрок самостоятельно принимает решения и выполняет игровые действия с бесплатными условными фишками. " +
                "В текущем APK-кандидате действия во внешнем 1win пока отключены; распознавание можно испытывать, " +
                "полный тест действия — внутри нашего клиента. Подключение ChatGPT Plus ещё не подтверждено."
        })
        button("НАЧАТЬ НАБЛЮДЕНИЕ ЭКРАНА 1WIN (без ставок)") { startOneTapObservation() }
        button("ПОДЕЛИТЬСЯ ЖУРНАЛОМ ОШИБОК (без изображений)") { shareObservationLog() }
        button("УДАЛИТЬ ЖУРНАЛ НАБЛЮДЕНИЙ") {
            ReadOnlySessionJournal.clear(this)
            Toast.makeText(this, "Журнал удалён", Toast.LENGTH_SHORT).show()
        }
        status = TextView(this).apply {
            id = R.id.captureStatus
            text = "Захват выключен"
            layout.addView(this)
        }
        button("1. Разрешить захват экрана") { requestCapture() }
        button("ОСТАНОВИТЬ ЗАХВАТ И УДАЛИТЬ КАДР") { stopCapture() }
        button("Показать последний кадр / статус потока") { refreshFrame() }
        headline("Непрерывное наблюдение с адаптивным JPEG")
        val qualityChoices = arrayOf("Быстрый · 720px / Q55", "Баланс · 960px / Q75", "Детали · 1280px / Q88", "Распознавание · 1536px / Q75")
        val qualitySelect = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, qualityChoices)
            setSelection(1)
            onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
                override fun onNothingSelected(parent: android.widget.AdapterView<*>?) = Unit
                override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: android.view.View?,
                                            position: Int, id: Long) { CaptureOptions.profile = position }
            }
            layout.addView(this)
        }
        button("НАЧАТЬ поток выбранных кадров к GPT") { startObserveStream() }
        button("БЫСТРЫЙ тест: кнопки и устойчивость сигнала (без ставок)") { startFastObserveStream() }
        button("ОСТАНОВИТЬ поток GPT (захват останется)") { stopObserveStream() }
        layout.addView(TextView(this).apply {
            text = "Поток — отдельные JPEG при изменениях, не видеозвонок. " +
                "После явного запуска наблюдение может продолжаться поверх других приложений. " +
                "Не открывайте пароли или платёжные данные во время захвата."
        })
        preview = ImageView(this).apply {
            adjustViewBounds = true
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 390)
            scaleType = ImageView.ScaleType.FIT_CENTER
            layout.addView(this)
        }
        headline("Связь с сервером ИИ")
        layout.addView(TextView(this).apply { text = "URL работающего сервера. 127.0.0.1 — сам телефон; для сервера на ПК нужен USB и adb reverse. Один адрес сервер не запускает. HTTPS поддерживается." })
        backend = EditText(this).apply {
            setSingleLine(true)
            id = R.id.backendUrl
            setText(getPreferences(Context.MODE_PRIVATE).getString("server_url", "http://127.0.0.1:8787"))
            layout.addView(this)
        }
        layout.addView(TextView(this).apply { text = "Секрет устройства (ARC_DEVICE_TOKEN):" })
        deviceToken = EditText(this).apply {
            id = R.id.deviceToken
            setSingleLine(true)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            hint = "Введите токен сервера"
            layout.addView(this)
        }
        button("2. БЕСПЛАТНО: проверить качество кадра (без GPT)") {
            analyzeOneFrame("/offline/inspect", "offline_inspect")
        }
        button("БЕСПЛАТНО: измерить задержку связи (без GPT и кадров)") {
            measureConnectionRtt()
        }
        layout.addView(TextView(this).apply {
            text = "7 запросов к локальному серверу: первый прогревочный. " +
                "Измеряется только HTTP RTT, не скорость распознавания и не игровая реакция."
        })
        headline("Бесплатная математика: вероятность появления аутов")
        layout.addView(TextView(this).apply {
            text = "Введите карты вручную: A K Q J T 9..2 + масть c/d/h/s. " +
                "Результат — вероятность увидеть заданную карту, НЕ шанс победы и НЕ совет по ставке."
        })
        heroCardsInput = EditText(this).apply {
            id = R.id.heroCards
            hint = "2 карты: Ah Kh"
            setSingleLine(true)
            layout.addView(this)
        }
        boardCardsInput = EditText(this).apply {
            id = R.id.boardCards
            hint = "Карты стола (0, 3, 4 или 5): Qh Jh 2c"
            setSingleLine(true)
            layout.addView(this)
        }
        outCardsInput = EditText(this).apply {
            id = R.id.outCards
            hint = "Ауты (неизвестные карты): 3h 4h 5h"
            setSingleLine(true)
            layout.addView(this)
        }
        button("БЕСПЛАТНО: точная вероятность аутов (без GPT)") {
            calculateOfflineDrawOdds(heroCardsInput.text.toString(),
                boardCardsInput.text.toString(), outCardsInput.text.toString())
        }
        Button(this).apply {
            id = R.id.recognizeCards
            text = "3. РАСПОЗНАТЬ КАРТЫ И ЗАПОЛНИТЬ ПОЛЯ"
            setOnClickListener { recognizeCardsFromFrame() }
            layout.addView(this)
        }
        layout.addView(TextView(this).apply {
            text = "Заполняются только подтверждённые карты руки и стола. " +
                "Ауты вычисляются отдельно; угадывать их по фотографии нельзя. " +
                "Для распознавания нужен работающий сервер /vision/cards."
        })
        button("2. Проанализировать 1 кадр через API") { analyzeOneFrame() }
        button("2A. Распознать экран покера (лобби / бай-ин / стол)") {
            analyzeOneFrame("/poker/screen", "poker_screen")
        }
        aiResult = TextView(this).apply {
            id = R.id.aiResult
            text = "Результат GPT или DEMO появится здесь. Автожесты — только по тестовой цели."
            setPadding(0, 12, 0, 18)
            layout.addView(this)
        }
        headline("Контроль версий ИИ — только просмотр")
        button("Проверить текущую версию ИИ") { fetchRuntimeStatus() }
        layout.addView(TextView(this).apply {
            text = "Обновление и откат отключены в приложении. " +
                "Смена профиля выполняется локально, в проверенном безопасном состоянии."
        })
        headline("Автономная сессия с калиброванными касаниями")
        layout.addView(TextView(this).apply {
            text = "Экспериментальный режим. Укажите фактическое имя пакета целевого приложения " +
                "и координаты центров кнопок как доли окна от 0 до 1. GPT не может изменять координаты. " +
                "Для Call/Raise требуется серверный лимит фишек. ОШИБКА распознавания может привести " +
                "к денежным потерям — не использовать на реальном балансе до проверок на устройстве."
        })
        expectedGameApp=EditText(this).apply {
            hint="Имя пакета приложения (например, com.example.game)"
            setSingleLine(true)
            layout.addView(this)
        }
        calibratedButtons=EditText(this).apply {
            hint="JSON центров: {\"fold\":[x,y],\"check\":[x,y],...}"
            minLines=2; maxLines=5
            layout.addView(this)
        }
        button("ВНЕШНИЕ ДЕЙСТВИЯ В LAB ОТКЛЮЧЕНЫ") {
            aiResult.text = "Лабораторная сборка v2.12: внешнее управление отключено"
        }
        button("ЛОКАЛЬНЫЙ ТЕСТ решения Raise (80 условных фишек)") {
            val sample = PlayChipTurnGuard.Turn("local-test-hand", 1L, 120L, true, true, true,
                setOf("fold", "call", "raise"), 20, 60, 120, 150, true)
            val action = PlayChipTurnGuard.Move("local-test-hand", 1L, "raise", 80)
            val granted = playChipTurnGuard.authorize(sample, action)
            aiResult.text = if (granted) "ПРОТОКОЛ: Raise 80 прошёл проверку; это локальный тест, касание 1win НЕ выполнено"
                else "Команда отклонена: STOP, повтор или нарушение ограничений"
        }
        button("СТОП ВНЕШНЕГО ИИ-АГЕНТА") { stopPokerSession() }
        button("ПОКАЗАТЬ СТАТУС АГЕНТА") { aiResult.text=FrameStore.gameStatus }
        layout.addView(TextView(this).apply {
            text="Видимое уведомление Android содержит СТОП ЗАХВАТ — оно немедленно " +
                "завершает сессию. По умолчанию сервер блокирует денежные действия. " +
                "Обработка экрана GPT требует отдельного OpenAI API-ключа."
        })
        headline("Автономный GPT-тест — внутри этого приложения")
        button("3. Открыть настройки специальных возможностей") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        testTarget = Button(this).apply {
            id = R.id.testTarget
            text = "ТЕСТОВАЯ ЦЕЛЬ: 0 касаний. ЗАДАЧА: нажми 1 раз."
            setOnClickListener {
                tapCount++
                text = "ТЕСТОВАЯ ЦЕЛЬ: $tapCount касаний. ГОТОВО."
            }
            layout.addView(this)
        }
        button("4. Выполнить тестовое касание") {
            val ok = DemoAccessibilityService.tapOwnDemoButton()
            Toast.makeText(this, if (ok) "Жест отправлен" else
                "Включите службу и откройте экран приложения", Toast.LENGTH_LONG).show()
        }
        button("5. ЗАПУСТИТЬ ПОЛНЫЙ ЦИКЛ GPT (1 тестовое касание)") { startAgentCycle() }
        button("СТОП ИИ-АГЕНТА") { stopAgentCycle("Остановлено пользователем") }
        layout.addView(TextView(this).apply {
            text = "Тестовая цель работает без внешнего приложения. Новый внешний режим " +
                "отдельно проверяет пакет окна, координаты и лимиты. Без OPENAI_API_KEY " +
                "сервер не разрешает внешних действий."
            setPadding(0, 12, 0, 0)
        })
    }

    private fun measureConnectionRtt() {
        val connection = validEndpoint()
        if (connection == null) {
            aiResult.text = "Нужен допустимый URL сервера и токен не короче 12 символов"
            return
        }
        val (base, token) = connection
        aiResult.text = "Проверяю связь без передачи изображений…"
        thread(name = "OfflineRttDiagnostic", isDaemon = true) {
            val successes = mutableListOf<Long>()
            var failures = 0
            var lastError = ""
            repeat(7) { index ->
                val start = android.os.SystemClock.elapsedRealtimeNanos()
                var conn: HttpURLConnection? = null
                try {
                    conn = (URL("$base/diagnostics/ping").openConnection() as HttpURLConnection).apply {
                        requestMethod = "GET"
                        setRequestProperty("X-Device-Token", token)
                        setRequestProperty("Cache-Control", "no-cache")
                        connectTimeout = 3000
                        readTimeout = 3000
                        useCaches = false
                    }
                    val code = conn.responseCode
                    val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                        ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
                    val response = JSONObject(body)
                    if (code != 200 || response.optString("mode") != "offline_connection_diagnostic" ||
                        response.optString("status") != "ok" || !response.isNull("action") ||
                        response.optBoolean("money_actions_enabled", true) ||
                        response.optBoolean("uses_openai_api", true)) {
                        throw IllegalStateException("Некорректный ответ: HTTP $code")
                    }
                    // First request warms up the connection and is not included in statistics.
                    if (index > 0) successes.add(
                        (android.os.SystemClock.elapsedRealtimeNanos() - start) / 1_000_000
                    )
                } catch (e: Exception) {
                    if (index > 0) failures++
                    lastError = e.javaClass.simpleName
                } finally {
                    conn?.disconnect()
                }
            }
            val report = RttSummary.fromSamples(successes, failures)
            val text = if (report.successes == 0) {
                "Сервер недоступен: ${report.failures} ошибок. Последняя: $lastError"
            } else {
                "Связь (только HTTP, без GPT): ${report.successes}/6 ответов; " +
                    "ошибок: ${report.failures}; медиана: ${report.medianMs} мс; " +
                    "p95: ${report.p95Ms} мс; min/max: ${report.minimumMs}/${report.maximumMs} мс; " +
                    "качество: ${report.quality}. Это НЕ задержка игрового решения."
            }
            runOnUiThread { aiResult.text = text }
        }
    }

    private fun fetchRuntimeStatus() {
        val connection = validEndpoint()
        if (connection == null) { aiResult.text="Неверный сервер или токен"; return }
        val (base, token) = connection
        aiResult.text="Запрашиваю проверенную версию ИИ…"
        thread(name="RuntimeVersionReadOnly", isDaemon=true) {
            val outcome = try {
                val connectionHttp = (URL("$base/runtime/status").openConnection() as HttpURLConnection).apply {
                    requestMethod="GET"
                    setRequestProperty("X-Device-Token", token)
                    connectTimeout=10000
                    readTimeout=15000
                }
                try {
                    val code=connectionHttp.responseCode
                    val stream=if (code in 200..299) connectionHttp.inputStream else connectionHttp.errorStream
                    val raw=stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
                    val data=JSONObject(raw)
                    if (code in 200..299) {
                        "ИИ: ${data.optString("policy_name")}\n" +
                        "Контрольная точка: ${data.optString("checkpoint")}\n" +
                        "Релиз: ${data.optString("release")}\n" +
                        "Лабораторный профиль: ${data.optBoolean("lab_only")}\n" +
                        "Денежные команды этого модуля: выключены"
                    } else "HTTP $code: ${data.optString("error","ошибка")}" 
                } finally { connectionHttp.disconnect() }
            } catch (e: Exception) { "Версия недоступна: ${e.message}" }
            runOnUiThread { aiResult.text=outcome }
        }
    }

    private fun startPokerSession() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) { aiResult.text = "СТОП: сначала разрешите новую сессию"; return }
        if (!BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED) {
            aiResult.text = "Внешние действия отключены в лабораторной сборке"
            return
        }
        val connection=validEndpoint()
        if (connection==null) { aiResult.text="Неверный сервер или токен"; return }
        if (!FrameStore.isCapturing) { aiResult.text="Разрешите захват экрана"; return }
        if (!DemoAccessibilityService.enabled()) { aiResult.text="Включите Accessibility-службу"; return }
        val pkg=expectedGameApp.text.toString().trim()
        val buttons=calibratedButtons.text.toString().trim()
        if (!pkg.matches(Regex("[a-zA-Z0-9_.]{5,120}")) || pkg==packageName) {
            aiResult.text="Введите корректное имя пакета целевого приложения"
            return
        }
        try {
            val config=JSONObject(buttons)
            require(listOf("fold","check","call","raise").any { config.has(it) })
        } catch (_: Exception) {
            aiResult.text="Введите JSON с координатами хотя бы одной кнопки"
            return
        }
        val (base,token)=connection
        startService(Intent(this,CaptureService::class.java).apply {
            action=CaptureService.ACTION_POKER_START
            putExtra(CaptureService.EXTRA_BASE_URL,base)
            putExtra(CaptureService.EXTRA_TOKEN,token)
            putExtra(CaptureService.EXTRA_POKER_PACKAGE,pkg)
            putExtra(CaptureService.EXTRA_BUTTON_LAYOUT,buttons)
        })
        aiResult.text="Сессия запрошена. Переключитесь в целевое приложение; уведомление позволяет остановить захват."
    }

    private fun stopPokerSession() {
        playChipTurnGuard.stop()
        startService(Intent(this,CaptureService::class.java).setAction(CaptureService.ACTION_POKER_STOP))
        aiResult.text="Запрошена остановка внешней сессии"
    }

    /** One explicit user gesture prepares capture + read-only analysis for a real UI. */
    private fun startOneTapObservation() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) { status.text = "СТОП: сначала разрешите новую сессию"; return }
        if (validEndpoint() == null) {
            status.text = "Проверьте адрес сервера и токен; для USB используйте adb reverse tcp:8787 tcp:8787"
            return
        }
        if (FrameStore.isCapturing) {
            startFastObserveStream()
            status.text = "Наблюдение запущено. Теперь откройте 1win. Нажатия в 1win отключены."
        } else {
            readOnlyStartPending = true
            requestCapture()
        }
    }

    private fun waitForReadOnlyCapture(attempt: Int = 0) {
        if (!readOnlyStartPending) return
        if (FrameStore.isCapturing && FrameStore.latestJpeg != null) {
            readOnlyStartPending = false
            startFastObserveStream()
            status.text = "Наблюдение включено. Теперь переключитесь в 1win; для остановки есть уведомление."
            return
        }
        if (attempt >= 40) {
            readOnlyStartPending = false
            status.text = "Кадр не получен за 10 секунд: ${FrameStore.captureError}"
            return
        }
        uiHandler.postDelayed({ waitForReadOnlyCapture(attempt + 1) }, 250L)
    }

    private fun shareObservationLog() {
        val report = ReadOnlySessionJournal.read(this)
        if (report.isBlank()) {
            Toast.makeText(this, "Журнал пока пуст", Toast.LENGTH_SHORT).show()
            return
        }
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, "AI Remote Control — журнал наблюдений")
            putExtra(Intent.EXTRA_TEXT, report.takeLast(70_000))
        }
        startActivity(Intent.createChooser(send, "Передать журнал наблюдений"))
    }

    private fun requestCapture() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) {
            if (::status.isInitialized) status.text = "СТОП: для нового захвата разрешите сессию"
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), notificationRequest)
            return
        }
        showCaptureDialog()
    }
    private fun showCaptureDialog() {
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        startActivityForResult(manager.createScreenCaptureIntent(), projectionRequest)
    }

    @Deprecated("Legacy activity result used for a dependency-free Android demo")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == projectionRequest && resultCode == RESULT_OK && data != null) {
            stopService(Intent(this, CaptureService::class.java))
            FrameStore.clear()
            val intent = Intent(this, CaptureService::class.java).apply {
                action = CaptureService.ACTION_START
                putExtra(CaptureService.EXTRA_RESULT_CODE, resultCode)
                putExtra(CaptureService.EXTRA_DATA, data)
            }
            startForegroundService(intent)
            status.text = "Захват запускается…"
            if (readOnlyStartPending) waitForReadOnlyCapture()
        } else if (requestCode == projectionRequest) {
            readOnlyStartPending = false
            status.text = "Пользователь отменил разрешение захвата"
        }
    }

    override fun onRequestPermissionsResult(req: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(req, permissions, results)
        if (req == notificationRequest) showCaptureDialog()
    }

    private fun stopCapture() {
        readOnlyStartPending = false
        stopAgentCycle("Захват остановлен")
        stopPokerSession()
        stopService(Intent(this, CaptureService::class.java))
        FrameStore.clear()
        preview.setImageDrawable(null)
        status.text = "Захват остановлен; сохранённый кадр очищен"
    }

    private fun refreshFrame() {
        val bytes = FrameStore.latestJpeg
        if (bytes == null) {
            status.text = "Кадра ещё нет. ${FrameStore.captureError}"
            return
        }
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        preview.setImageBitmap(bitmap)
        status.text = "JPEG: ${bytes.size / 1024} КиБ, " +
            "${FrameStore.latest?.width}×${FrameStore.latest?.height}, " +
            "Q${FrameStore.latest?.quality}, поток: ${FrameStore.isStreaming}\n${FrameStore.streamStatus}"
    }

    private fun startFastObserveStream() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) { status.text = "СТОП: сначала разрешите сессию"; return }
        // Dedicated read-only fast loop; same consent and token as regular stream.
        val connection = validEndpoint()
        if (!FrameStore.isCapturing || connection == null) {
            aiResult.text = "Сначала разрешите захват и настройте безопасный адрес сервера/токен"
            return
        }
        val (base, token) = connection
        startService(Intent(this, CaptureService::class.java).apply {
            action = CaptureService.ACTION_FAST_START
            putExtra(CaptureService.EXTRA_BASE_URL, base)
            putExtra(CaptureService.EXTRA_TOKEN, token)
        })
        aiResult.text = "Запущен быстрый локальный режим: ~2 кадра/с; ставки выключены"
    }

    private fun startObserveStream() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) { status.text = "СТОП: сначала разрешите сессию"; return }
        val connection = validEndpoint()
        if (connection == null) { status.text = "Неверный URL сервера или токен"; return }
        if (!FrameStore.isCapturing) { status.text = "Сначала разрешите захват экрана"; return }
        val (base, token) = connection
        startService(Intent(this, CaptureService::class.java).apply {
            action = CaptureService.ACTION_STREAM_START
            putExtra(CaptureService.EXTRA_BASE_URL, base)
            putExtra(CaptureService.EXTRA_TOKEN, token)
        })
        status.text = "Запрошен запуск потока. Статус: кнопка 'Показать последний кадр'."
    }

    private fun stopObserveStream() {
        startService(Intent(this, CaptureService::class.java).setAction(CaptureService.ACTION_STREAM_STOP))
        status.text = "Поток остановлен (захват остаётся активным)"
    }

    private fun calculateOfflineDrawOdds(heroText: String, boardText: String, outsText: String) {
        val hero: List<String>
        val board: List<String>
        val outs: List<String>
        try {
            hero = ManualCardInput.tokens(heroText)
            board = ManualCardInput.tokens(boardText)
            outs = ManualCardInput.tokens(outsText)
        } catch (e: IllegalArgumentException) {
            aiResult.text = "Ошибка ввода: ${e.message}"
            return
        }
        if (hero.size != 2 || board.size !in 3..4) {
            aiResult.text = "Нужно ровно 2 карты руки и 3 либо 4 карты стола"
            return
        }
        val base = backend.text.toString().trim().trimEnd('/')
        val secret = deviceToken.text.toString()
        val endpoint = try { URI(base) } catch (_: Exception) { null }
        val allowedLocal = BuildConfig.DEBUG && endpoint?.scheme == "http" &&
            endpoint.host in setOf("127.0.0.1", "10.0.2.2") &&
            endpoint.port == 8787 && endpoint.rawUserInfo == null
        val allowedTls = endpoint?.scheme == "https" && endpoint.host != null &&
            endpoint.rawUserInfo == null
        if ((!allowedTls && !allowedLocal) || secret.length < 12) {
            aiResult.text = "Нужен HTTPS (либо локальный DEBUG:8787) и токен от 12 символов"
            return
        }
        aiResult.text = "Вычисляю точную вероятность локально, без GPT…"
        thread(name = "OfflineDrawOdds", isDaemon = true) {
            val result = try {
                val conn = (URL("$base/math/draw-odds").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("X-Device-Token", secret)
                    connectTimeout = 10000
                    readTimeout = 10000
                    doOutput = true
                }
                val body = JSONObject().apply {
                    put("request", "math_draw_odds")
                    put("hero_cards", JSONArray(hero))
                    put("board_cards", JSONArray(board))
                    put("outs_cards", JSONArray(outs))
                }
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val response = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
                conn.disconnect()
                val parsed = JSONObject(response)
                if (code in 200..299) {
                    val next = parsed.getDouble("hit_next_card_probability") * 100
                    val river = parsed.getDouble("hit_by_river_probability") * 100
                    "Вероятность увидеть один из заданных аутов:\n" +
                        "Следующая карта: %.2f%%\nК риверу: %.2f%%\n".format(next, river) +
                        "Без GPT и ставок. Ауты указаны вручную и могут не гарантировать победу."
                } else "Сервер: HTTP $code — ${parsed.optString("error", "ошибка")}"
            } catch (e: Exception) { "Ошибка расчёта: ${e.message}" }
            runOnUiThread { aiResult.text = result }
        }
    }

    /** Read-only offline vision. Fills manual fields only after a COMPLETE verified observation. */
    private fun recognizeCardsFromFrame(attempt: Int = 0) {
        if (OperatorStopStore.isStopped(this) || !FrameStore.isCapturing) {
            aiResult.text = "Сначала разрешите сессию и захват экрана"
            return
        }
        // The 960px preset produces only ~443px width on this phone and the CV
        // reader deliberately rejects it. Request a NEW full-detail frame first.
        if (FrameStore.latest?.profile != 3) {
            CaptureOptions.profile = 3
            if (attempt >= 25) {
                aiResult.text = "Нет нового кадра высокого качества. Обновите изображение захватываемого экрана."
                return
            }
            val generation = recognitionGeneration.get()
            aiResult.text = "Ожидаю новый кадр 1536px для распознавания карт…"
            uiHandler.postDelayed({
                if (!isDestroyed && generation == recognitionGeneration.get()) recognizeCardsFromFrame(attempt + 1)
            }, 200L)
            return
        }
        val snapshot = FrameStore.latest
        val frame = snapshot?.jpeg?.clone()
        if (frame == null || !FrameStore.isCapturing || OperatorStopStore.isStopped(this)) {
            aiResult.text = "Сначала разрешите сессию, захват и получите кадр"
            return
        }
        val endpoint = validEndpoint()
        if (endpoint == null) {
            aiResult.text = "Нужен работающий сервер (127.0.0.1 — это сам телефон) и токен от 12 символов. " +
                "Проверка качества не распознаёт карты."
            return
        }
        if (!recognitionBusy.compareAndSet(false, true)) return
        val generation = recognitionGeneration.get()
        val (base, secret) = endpoint
        aiResult.text = "Локальное распознавание кадра без GPT…"
        thread(name = "ReadOnlyCardRecognition", isDaemon = true) {
            var fill: CardAutoFill.Cards? = null
            val result = try {
                val conn = (URL("$base/vision/cards").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("X-Device-Token", secret)
                    connectTimeout = 5000
                    readTimeout = 15000
                    doOutput = true
                }
                try {
                    val payload = JSONObject().apply {
                        put("request", "vision_cards")
                        put("image_base64", Base64.getEncoder().encodeToString(frame))
                        put("screen_state", "live_table")
                    }
                    conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
                    val code = conn.responseCode
                    val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                    val json = JSONObject(stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}")
                    if (code !in 200..299) {
                        "Сервер вернул HTTP $code: ${json.optString("error", "ошибка")}"
                    } else {
                        fun values(name: String): List<String> {
                            val arr = json.optJSONArray(name) ?: return emptyList()
                            return (0 until arr.length()).map { arr.optString(it, "") }
                        }
                        fill = CardAutoFill.checked(
                            json.optString("quality"), json.optString("screen_state"),
                            values("hero_cards"), values("board_cards"))
                        if (fill == null) {
                            "Карты не подтверждены: ${json.optString("reason", "недостаточная точность")}. " +
                                "Поля оставлены без изменений. Нужен более чёткий кадр."
                        } else "Карты распознаны и проверены (локально, без GPT). Ауты не определялись."
                    }
                } finally { conn.disconnect() }
            } catch (e: Exception) { "Не удалось распознать карты: ${e.message}. Проверьте сервер и токен." }
            runOnUiThread {
                recognitionBusy.set(false)
                if (isDestroyed || generation != recognitionGeneration.get() || OperatorStopStore.isStopped(this)) return@runOnUiThread
                if (snapshot?.seq != FrameStore.latest?.seq) {
                    aiResult.text = "Кадр изменился во время распознавания. Повторите запрос."
                    return@runOnUiThread
                }
                if (fill != null && FrameStore.isCapturing && !OperatorStopStore.isStopped(this)) {
                    heroCardsInput.setText(fill!!.hero.joinToString(" "))
                    boardCardsInput.setText(fill!!.board.joinToString(" "))
                    // Old outs belong to an earlier hand; never carry them into a new observation.
                    outCardsInput.text.clear()
                }
                aiResult.text = result
            }
        }
    }

    private fun analyzeOneFrame(path: String = "/analyze", task: String = "describe") {
        val frame = FrameStore.latestJpeg?.clone()
        if (frame == null || !FrameStore.isCapturing) {
            aiResult.text = "Сначала разрешите захват и получите кадр"
            return
        }
        val base = backend.text.toString().trim().trimEnd('/')
        val secret = deviceToken.text.toString()
        val endpoint = try { URI(base) } catch (_: Exception) { null }
        val allowedLocal = BuildConfig.DEBUG && endpoint?.scheme == "http" &&
            endpoint.host in setOf("127.0.0.1", "10.0.2.2") &&
            endpoint.port == 8787 && endpoint.rawUserInfo == null
        val allowedTls = endpoint?.scheme == "https" && endpoint.host != null &&
            endpoint.rawUserInfo == null
        if ((!allowedTls && !allowedLocal) || secret.length < 12) {
            aiResult.text = "Нужен HTTPS (либо локальный DEBUG:8787) и токен длиной от 12 символов"
            return
        }
        aiResult.text = "Отправляю один кадр на анализ…"
        thread(name = "AIAnalysis", isDaemon = true) {
            val outcome = try {
                val url = URL("$base$path")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("X-Device-Token", secret)
                    connectTimeout = 10000
                    readTimeout = 45000
                    doOutput = true
                }
                val json = JSONObject().apply {
                    put("image_base64", Base64.getEncoder().encodeToString(frame))
                    put("request", task)
                }
                conn.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val response = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
                conn.disconnect()
                val parsed = JSONObject(response)
                if (code in 200..299) {
                    if (task == "offline_inspect") {
                        "Локальная диагностика (без GPT и оплаты API):\n" + parsed.toString(2)
                    } else if (task == "poker_screen") {
                        val obs=parsed.optJSONObject("observation")
                        val advice=parsed.optJSONObject("recommendation")
                        "Распознавание GPT (только чтение):\n" +
                            (obs?.toString(2) ?: "Нет данных") +
                            "\n\nОценка столов/бай-ина:\n" +
                            (advice?.toString(2) ?: "Нет рекомендации")
                    } else "Режим: ${parsed.optString("mode")}\n${parsed.optString("summary")}"
                } else "Сервер: HTTP $code — ${parsed.optString("error", "ошибка") }"
            } catch (e: Exception) { "Ошибка соединения: ${e.message}" }
            runOnUiThread { aiResult.text = outcome }
        }
    }

    override fun onResume() {
        super.onResume()
        appForeground = true
        // Also observe a STOP issued from the persistent foreground notification.
        if (OperatorStopStore.isStopped(this)) {
            operatorControl.stop()
            stopAgentCycle("Оператор остановил сессию — требуется новое разрешение")
        }
    }

    override fun onPause() {
        // Explicit foreground-only control; it never operates unattended in other apps.
        appForeground = false
        if (agentRunning.get()) stopAgentCycle("Приложение потеряло фокус")
        super.onPause()
    }

    private fun emergencyStop() {
        // No acknowledgement dialog: the operator's decision is immediate.
        operatorControl.stop()
        // Store STOP before sending an intent: service and Accessibility must fail closed.
        OperatorStopStore.stop(this)
        readOnlyStartPending = false
        recognitionGeneration.incrementAndGet()
        playChipTurnGuard.stop()
        stopAgentCycle("АВАРИЙНЫЙ СТОП: для новой сессии требуется ручное разрешение")
        // Stops MediaProjection, uploaders and any running session; clears stored screenshot.
        startService(Intent(this, CaptureService::class.java).setAction(CaptureService.ACTION_STOP))
        FrameStore.clear()
        if (::status.isInitialized) status.text = "АВАРИЙНЫЙ СТОП — захват и поток отключены"
    }

    private fun stopAgentCycle(message: String) {
        cycleVersion.incrementAndGet()
        agentRunning.set(false)
        if (::aiResult.isInitialized) aiResult.text = message
    }

    private fun validEndpoint(): Pair<String, String>? {
        val base = backend.text.toString().trim().trimEnd('/')
        val secret = deviceToken.text.toString()
        val endpoint = try { URI(base) } catch (_: Exception) { null }
        val localhost = BuildConfig.DEBUG && endpoint?.scheme == "http" &&
            endpoint.host in setOf("127.0.0.1", "10.0.2.2") && endpoint.port == 8787
        val secure = endpoint?.scheme == "https" && endpoint.host != null
        if ((!localhost && !secure) || endpoint?.rawUserInfo != null || secret.length < 12) return null
        getPreferences(Context.MODE_PRIVATE).edit().putString("server_url", base).apply()
        return Pair(base, secret)
    }

    private fun nextSandboxAction(base: String, secret: String, count: Int, frame: ByteArray): JSONObject {
        val endpoint = URL("$base/demo/next")
        val connection = (endpoint.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("X-Device-Token", secret)
            connectTimeout = 10000
            readTimeout = 45000
            doOutput = true
        }
        try {
            val message = JSONObject().apply {
                put("request", "demo_next")
                put("image_base64", Base64.getEncoder().encodeToString(frame))
                put("sandbox_state", JSONObject().put("tap_count", count))
            }
            connection.outputStream.use { it.write(message.toString().toByteArray(Charsets.UTF_8)) }
            val httpCode = connection.responseCode
            val stream = if (httpCode in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
            if (httpCode !in 200..299) throw IllegalStateException("HTTP $httpCode: $text")
            return JSONObject(text)
        } finally { connection.disconnect() }
    }

    private fun startAgentCycle() {
        if (!(operatorControl.mayStart() && !OperatorStopStore.isStopped(this))) { aiResult.text = "СТОП: сначала разрешите новую сессию"; return }
        if (agentRunning.get()) return
        val connection = validEndpoint()
        if (connection == null) { aiResult.text = "Проверь адрес сервера и токен устройства"; return }
        if (!FrameStore.isCapturing) { aiResult.text = "Сначала разреши захват экрана"; return }
        if (!DemoAccessibilityService.enabled()) { aiResult.text = "Сначала включи тестовую Accessibility-службу"; return }
        if (!appForeground) return
        tapCount = 0
        testTarget.text = "ТЕСТОВАЯ ЦЕЛЬ: 0 касаний. ЗАДАЧА: нажми 1 раз."
        agentRunning.set(true)
        val version = cycleVersion.incrementAndGet()
        aiResult.text = "ИИ запущен: наблюдение → решение → тестовое касание → проверка"
        val (base, secret) = connection
        thread(name = "SandboxAgent", isDaemon = true) {
            try {
                // Only two observations and at most one locally authorized gesture.
                Thread.sleep(1700)
                for (step in 0..1) {
                    if (!isCurrentCycle(version)) return@thread
                    if (!DemoAccessibilityService.isOwnAppActive())
                        throw IllegalStateException("Не найдено активное окно собственного приложения")
                    val frame = FrameStore.latestJpeg?.clone() ?: throw IllegalStateException("Нет свежего JPEG")
                    val sequenceBefore = FrameStore.frameSequence
                    val count = tapCount
                    val plan = nextSandboxAction(base, secret, count, frame)
                    if (!isCurrentCycle(version)) return@thread
                    if (plan.optString("scope") != "own_app_only") throw IllegalStateException("Недопустимая область действия")
                    val mode = plan.optString("mode")
                    val action = plan.optString("action")
                    updateCycle(version, "Шаг ${step + 1}: $mode → $action. ${plan.optString("reason")}")
                    when (action) {
                        "tap_own_test_button" -> {
                            if (step != 0 || count != 0) throw IllegalStateException("Повторное касание запрещено")
                            if (!DemoAccessibilityService.tapOwnDemoButtonBlocking())
                                throw IllegalStateException("Служба не выполнила тестовый жест")
                            val deadline = System.currentTimeMillis() + 3000
                            while (isCurrentCycle(version) && tapCount != 1 && System.currentTimeMillis() < deadline)
                                Thread.sleep(100)
                            if (!isCurrentCycle(version)) return@thread
                            if (tapCount != 1) throw IllegalStateException("Контроль не подтвердил касание")
                            // Must get a NEW screenshot after the gesture before asking the model again.
                            val frameDeadline = System.currentTimeMillis() + 3500
                            while (isCurrentCycle(version) && FrameStore.frameSequence <= sequenceBefore &&
                                   System.currentTimeMillis() < frameDeadline) Thread.sleep(100)
                            if (!isCurrentCycle(version)) return@thread
                            if (FrameStore.frameSequence <= sequenceBefore)
                                throw IllegalStateException("Не получен новый снимок после действия")
                        }
                        "finish" -> {
                            if (tapCount != 1) throw IllegalStateException("Модель завершила тест до результата")
                            updateCycle(version, "УСПЕХ: агент подтвердил завершение теста после нового снимка ($mode)")
                            agentRunning.set(false)
                            return@thread
                        }
                        "wait" -> throw IllegalStateException("GPT не распознал демонстрационное окно; тест остановлен")
                        else -> throw IllegalStateException("Недопустимое действие GPT")
                    }
                }
                throw IllegalStateException("Цикл не завершился за 2 наблюдения")
            } catch (e: Exception) {
                updateCycle(version, "ИИ остановлен безопасно: ${e.message}")
            } finally {
                if (cycleVersion.get() == version) agentRunning.set(false)
            }
        }
    }

    private fun isCurrentCycle(version: Int): Boolean =
        agentRunning.get() && appForeground && FrameStore.isCapturing && cycleVersion.get() == version

    private fun updateCycle(version: Int, text: String) {
        runOnUiThread { if (cycleVersion.get() == version) aiResult.text = text }
    }

}
