# v2.11 Persistent Operator STOP (2026-10-17)

- Добавлена сохраняемая между процессами аварийная остановка `OperatorStopStore.kt` (default STOP).
- Единая проверка STOP в Android Activity, MediaProjection foreground service и тестовом Accessibility executor.
- STOP из системного уведомления сохраняет состояние до остановки потоков.
- После перезапуска приложения или переключения в foreground сохраняемая остановка применяется в UI.
- Windows APK-сборка сначала запускает Gradle `:app:testDebugUnitTest`.
- Исправлены тесты статических сборочных ограничений: перед отрицательным тестом теперь проверяется исправность фикстуры.
- Обновлены release gate, versionName `2.11.0-persistent-stop`, versionCode `31`, CI/Windows имена артефактов.
- Добавлен изолированный тест хранилища STOP на подставном `android.content.Context` без требования Android SDK.
- Не изменено: `EXTERNAL_GAME_ACTIONS_ENABLED=false`, запрет внешних касаний в текущей лабораторной сборке.
- Ограничения: APK не собран, ChatGPT Plus не авторизован, 1win не испытан на телефоне.
