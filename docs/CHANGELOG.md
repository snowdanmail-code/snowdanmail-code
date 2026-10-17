## v1.0

- Independent Hold’em math evaluator, equity against uniform random opponent, bounded offline HTTP API.
- Structural checks for cards and screen phases; cross-frame hand timeline verifier.
- No live GPT API inference, Android APK, or new real-money actions enabled.

# Изменения v0.8 относительно v0.7

- `server/arc_runtime/release.py` — read-only разрешение активного релиза, строгая JSON-схема политики, проверка SHA-256 и свидетельств тестов.
- `server/arc_runtime/observe.py` — конечный автомат, ограничение памяти сессий, класс «настоящие сидящие игроки» vs «участники текущей руки», фильтр реплея.
- `server/arc_runtime/service.py` — потокобезопасное чтение версии и применение политики без перезапуска сервера.
- `server/arc_runtime/frame_hints.py` — вспомогательные признаки цвета/геометрии с воздержанием от низкоуверенных выводов, не OCR.
- `server/arc_runtime/adapter.py` — адаптация старых GPT-observation без придумывания отсутствующих полей.
- `server/arc_runtime/seed.py` — 2 **лабораторных** профиля для испытания реального переключения конфигураций.
- `server/server.py` — только читающие `/runtime/status`, `/runtime/observe`, `/runtime/frame-hint` и необязательное подключение старого `/poker/screen` к наблюдателю.
- `android/MainActivity.kt` — отображение версии и контрольной точки из API (Android SDK-тест ещё нужен).
- `server/lobby_agent.py` — дополнительные экраны replay/disconnected/seat_selection и др.
- `server/tests` — тесты границ, несовместимости, конкурентности и HTTP.

## v1.2 — Read-only money labels + composite vision

- Replaceable `TemplateMoneyReader` with anonymous 0–9 digit atlas, strict caption/currency checks, explicit abstention.
- New `CompositeObserver` only forwards confirmed hero/board cards to the existing Hold'em math engine; no betting action output.
- Read-only authenticated `/vision/measure` route.
- Private HUD-only screenshot and video crops for regression, plus explicit cv2/numpy dependencies.
- No APK or live game interaction; no confirmed full-card generalization or seat-level bet reading.
