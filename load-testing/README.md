# Voice Translation Load Test Plan

## Цели
- Зафиксировать опорные показатели для `/voice-translate` (p95 латентность транскрибации/перевода).
- Проверить устойчивость rate limiting с учётом `VOICE_RATE_LIMIT_WEIGHT`.
- Убедиться, что при деградации OpenAI сервисов корректно возвращаются 429/502 и метрики `voice_*` отражают инцидент.

## Инструменты
- [k6](https://k6.io/) — нагрузочные сценарии (`voice.k6.js`).
- Playwright — end-to-end сценарии с реальной записью через MediaRecorder для смоук-проверки после нагрева.
- Prometheus/Grafana — отслеживание `voice_requests_total`, `voice_latency_seconds`, `voice_detected_language_total`.

## Подготовка
1. Собрать короткий webm-файл (≤30 секунд) и сохранить рядом с планом как `sample.webm` или указать путь через `AUDIO_FILE`.
2. Экспортировать переменные окружения:
   ```bash
   export API_URL="https://staging.api.example.com"
   export API_USER="load-test"
   export API_TOKEN="$(curl -s -X POST "$API_URL/auth/token?user_id=load-test" | jq -r .access_token)"
   export AUDIO_FILE="/path/to/sample.webm"
   export TARGET_LANGS="ru,en,de"
   ```
3. Убедиться, что Prometheus и Grafana доступны; включить сохранение метрик за период теста.

## Запуск k6
```bash
k6 run load-testing/voice.k6.js \
  --vus 20 \
  --duration 10m
```
Или использовать встроенные стадии (по умолчанию 0→60 VU).

### Ожидаемые метрики
- `voice_transcription_latency_seconds{quantile="0.95"} < 2.0` секунд.
- `voice_translation_latency_seconds{quantile="0.95"} < 2.5` секунд.
- `voice_requests_total{status="api_error"}` ≈ 0 (при стабильном OpenAI).
- `rate_limit_blocked_total` не превышает установленных порогов (проверить `redis` ключи).

### Анализ результатов
1. Сравнить локальные Trends (`voice_transcription_latency`, `voice_translation_latency`) с Prometheus.
2. Проверить Grafana-панели: throughput, latency, распределение языков.
3. Зафиксировать вывод `k6` и экспортировать Prometheus snapshot (при необходимости приложить к отчёту).
4. Обновить `CHANGELOG` или внутренние заметки с новыми порогами.

## Playwright сценарий после нагрузки
1. Запустить `npm run test:e2e` в `frontend/` с включённым бэкендом.
2. Убедиться, что UI корректно отображает детектированный язык, confidence, латентности.
3. Проверить логи бэкенда — отсутствие всплесков ошибок после нагрузки.

## Эскалация и тюнинг
- При превышении порогов увеличить ресурсы Whisper/Responses (timeout, retries) либо поднять `VOICE_RATE_LIMIT_WEIGHT`.
- Зафиксировать найденные значения в Prometheus alert rules (`VoiceLatencySpike`, `VoiceErrorBurst`).
- Обновить документацию (`DEPLOYMENT.md`, Grafana) при изменении порогов.
