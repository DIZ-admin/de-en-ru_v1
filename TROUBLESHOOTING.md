# Руководство по решению проблем (Troubleshooting)

## 🔧 Общие проблемы

### 1. "Cannot find implementation or library stub for module named 'pydantic'"

**Проблема:** IDE показывает ошибку типизации для pydantic и других модулей.

**Решение:**
```bash
# Backend
cd backend
poetry install --no-root
poetry run mypy app

# Убедитесь, что IDE использует правильный Python interpreter:
# VSCode: Ctrl+Shift+P → Python: Select Interpreter → выберите .venv/bin/python
# PyCharm: Settings → Project → Python Interpreter → выберите Poetry interpreter
```

### 2. "OPENAI_API_KEY must be set"

**Проблема:** Backend не запускается с ошибкой валидации конфигурации.

**Решение:**
```bash
# Проверьте, что .env файл существует и содержит ключ
cat backend/.env

# Если файла нет, создайте его:
cp backend/.env.example backend/.env

# Добавьте ваш OpenAI API ключ:
echo "OPENAI_API_KEY=sk-your-key-here" >> backend/.env

# Перезагрузите приложение
```

### 3. "Connection refused" при подключении к Redis

**Проблема:** Backend не может подключиться к Redis.

**Решение:**
```bash
# Проверьте, запущен ли Redis
redis-cli ping  # должен вернуть PONG

# Если Redis не запущен:
# macOS:
brew services start redis

# Linux:
sudo systemctl start redis-server

# Docker:
docker run -d -p 6379:6379 redis:latest

# Если Redis не нужен, отключите его:
# backend/.env: REDIS_ENABLED=false
```

### 4. "Port 8000 already in use"

**Проблема:** Backend не может запуститься, так как порт занят.

**Решение:**
```bash
# Найдите процесс, использующий порт 8000
lsof -i :8000

# Завершите процесс
kill -9 <PID>

# Или используйте другой порт
poetry run uvicorn app.main:app --port 8001
```

### 5. "Frontend cannot connect to backend"

**Проблема:** Frontend показывает ошибку подключения к API.

**Решение:**
```bash
# Проверьте, что backend запущен
curl http://localhost:8000/healthz

# Проверьте NEXT_PUBLIC_API_URL в frontend/.env.local
cat frontend/.env.local

# Если переменная неправильная, обновите её:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local

# Перезагрузите frontend
npm run dev
```

## 🧪 Проблемы с тестированием

### 6. "Tests fail with 'Cannot find module'"

**Проблема:** Тесты не находят модули.

**Решение:**
```bash
# Backend
cd backend
poetry install --no-root
poetry run pytest tests/

# Frontend
cd frontend
npm install
npm test
```

### 7. "Playwright tests timeout"

**Проблема:** E2E тесты зависают или падают с таймаутом.

**Решение:**
```bash
# Установите Playwright браузеры
npx playwright install

# Запустите тесты с увеличенным таймаутом
npm run test:e2e -- --timeout=60000

# Или запустите в headed режиме для отладки
npx playwright test --headed
```

## 🐳 Проблемы с Docker

### 8. "Docker build fails with 'poetry install' error"

**Проблема:** Docker сборка падает при установке зависимостей.

**Решение:**
```bash
# Проверьте, что poetry.lock актуален
cd backend
poetry lock --no-update

# Пересоберите образ
docker build -t translator-backend .

# Или используйте --no-cache
docker build --no-cache -t translator-backend .
```

### 9. "Docker Compose services don't communicate"

**Проблема:** Контейнеры не могут подключиться друг к другу.

**Решение:**
```bash
# Проверьте, что сервисы используют правильные имена хостов
# В docker-compose.yml используйте имена сервисов:
# backend → http://backend:8000
# frontend → http://frontend:3000

# Перезагрузите Docker Compose
docker-compose down
docker-compose up -d

# Проверьте логи
docker-compose logs backend
docker-compose logs frontend
```

## 🔐 Проблемы с безопасностью

### 10. "401 Unauthorized" при запросе к API

**Проблема:** API возвращает ошибку аутентификации.

**Решение:**
```bash
# Получите новый токен
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?user_id=demo" | jq -r '.access_token')

# Используйте токен в запросе
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","target_lang":"ru"}'

# Проверьте, что токен не истек (TTL 30 минут по умолчанию)
```

### 11. "429 Too Many Requests"

**Проблема:** API возвращает ошибку rate limiting.

**Решение:**
```bash
# Подождите перед следующим запросом (по умолчанию 60 секунд)
sleep 60

# Или увеличьте лимит в backend/.env
RATE_LIMIT_MAX_CALLS=240
RATE_LIMIT_WINDOW_SECONDS=60

# Для голосовых запросов учитывается вес (по умолчанию 3)
# Один голосовой запрос = 3 обычных запроса
```

## 🎤 Проблемы с голосовым переводом

### 12. "Microphone access denied"

**Проблема:** Frontend не может получить доступ к микрофону.

**Решение:**
```bash
# Проверьте разрешения браузера
# Chrome/Edge: Settings → Privacy and security → Site settings → Microphone

# Убедитесь, что сайт использует HTTPS (в production)
# Микрофон работает только на HTTPS или localhost

# Проверьте, что VOICE_ENABLED=true в backend/.env
```

### 13. "Voice transcription fails with 'Unsupported media type'"

**Проблема:** Backend отклоняет аудиофайл.

**Решение:**
```bash
# Проверьте поддерживаемые форматы в backend/.env
VOICE_ALLOWED_MIME_TYPES=["audio/webm","audio/ogg","audio/mpeg","audio/wav"]

# Убедитесь, что файл имеет правильный MIME тип
file -b --mime-type sample.webm

# Конвертируйте файл в поддерживаемый формат
ffmpeg -i input.mp3 -c:a libopus -b:a 128k output.webm
```

### 14. "Voice confidence too low"

**Проблема:** Система не может определить язык с достаточной уверенностью.

**Решение:**
```bash
# Проверьте качество аудио (без шума, четкая речь)
# Убедитесь, что язык соответствует одному из поддерживаемых (RU, EN, DE)

# Понизьте порог уверенности в backend/.env
VOICE_DETECTION_CONFIDENCE_THRESHOLD=0.5  # по умолчанию 0.7

# Или используйте явное указание языка в запросе
# Отправьте source_lang вместо auto-detection
```

## 📊 Проблемы с мониторингом

### 15. "Prometheus не собирает метрики"

**Проблема:** Prometheus не видит метрики от backend.

**Решение:**
```bash
# Проверьте, что backend запущен
curl http://localhost:8000/metrics

# Проверьте конфигурацию Prometheus (monitoring/prometheus.yml)
# Убедитесь, что targets указывают на правильный адрес

# Перезагрузите Prometheus
docker-compose restart prometheus

# Проверьте логи
docker-compose logs prometheus
```

## 📝 Логирование и отладка

### Включение debug логирования

```bash
# Backend
export LOG_LEVEL=DEBUG
poetry run uvicorn app.main:app --reload

# Frontend
export DEBUG=*
npm run dev
```

### Проверка конфигурации

```bash
# Backend
poetry run python -c "from app.config import get_settings; print(get_settings())"

# Frontend
console.log(process.env)
```

---

**Последнее обновление:** 19 октября 2025 г.

Если проблема не решена, создайте issue на GitHub: https://github.com/DIZ-admin/de-en-ru_v1/issues

