# Backend - OpenAI-First Approach

Минимальный backend для трехязычного переводчика, использующий только OpenAI SDK.

## 🎯 Философия

- **Максимум OpenAI SDK** — весь AI делегируется OpenAI Responses API
- **Минимум кода** — только auth, rate limit, metrics
- **Нет абстракций** — прямой вызов OpenAI API
- **Простота** — ~500 строк вместо 2000+

## 📦 Структура

```
backend/
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI app + routes (~200 LoC)
│   ├── config.py            # Settings (~50 LoC)
│   ├── auth.py              # JWT + rate limiting (~100 LoC)
│   └── translate.py         # OpenAI Responses API (~150 LoC)
├── pyproject.toml           # Dependencies (7 core packages)
├── .env.example             # Environment variables
└── README.md                # This file
```

## 🚀 Быстрый старт

### 1. Установка

```bash
cd backend
pip install poetry
poetry install --no-root
```

### 2. Конфигурация

```bash
cp .env.example .env
# Добавить OPENAI_API_KEY в .env
```

### 3. Запуск

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

## 🔑 API Endpoints

### Authentication

```bash
# Get JWT token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo"}'
```

### Translation (Sync)

```bash
# Translate
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "ru"
  }'
```

### Translation (Streaming)

```bash
# Stream translation
curl -X POST http://localhost:8000/translate/stream \
  -H "Authorization: Bearer <token>" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a long text...",
    "target_lang": "de"
  }'
```

### Monitoring

```bash
# Health check
curl http://localhost:8000/healthz

# Metrics (Prometheus)
curl http://localhost:8000/metrics
```

## 📊 Зависимости

1. **fastapi** — Web framework
2. **uvicorn** — ASGI server
3. **pydantic** — Validation
4. **pydantic-settings** — Settings management
5. **openai** — OpenAI SDK (единственный AI framework!)
6. **pyjwt** — JWT auth
7. **prometheus-client** — Metrics
8. **redis[hiredis]** — Кэш и rate limiting

## 🧪 Тестирование

```bash
# Запустить тесты с покрытием ≥80%
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Lint
poetry run ruff check app/
poetry run black app/
poetry run mypy app/
```

### Настройка окружения для MyPy

> Требуется Python 3.11 (совместим с `python = "^3.11"` в `pyproject.toml`).

```bash
cd backend
poetry env use python3.11      # указывает Poetry на системный Python 3.11
poetry install --no-root       # устанавливает runtime + dev зависимости

# Проверка типов
poetry run mypy app
```

Если предпочитаете вручную управлять виртуальными окружениями:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r <(poetry export --with dev --format=requirements.txt)
mypy app
```

## 🔒 Безопасность

- **JWT tokens** с коротким TTL (30 мин) + поддержка RS256 и ротации ключей
- **Rate limiting** (120 req/min по умолчанию) на Redis с fallback
- **Security headers** (CSP, HSTS, X-Frame-Options, Permissions-Policy)
- **CORS** whitelist по `ALLOWED_ORIGINS`
- **Input validation** через Pydantic

## 📈 Метрики

Доступны через `/metrics`:

- `translations_total` — количество запросов по статусам
- `translation_latency_seconds` — гистограмма задержки
- `translation_cache_hits_total` / `translation_cache_misses_total`
- `rate_limit_blocked_total` — отклонённые запросы

## 🚦 Production

### Docker

```bash
docker build -t translator-backend .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e JWT_SECRET_KEY=secret \
  translator-backend
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-...                    # Required
JWT_SECRET_KEY=change-me                 # Используется в режиме HS256
JWT_ALGORITHM=RS256                      # Рекомендуется RS256 в prod
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem
JWT_ADDITIONAL_PUBLIC_KEYS=
JWT_KID=current-key
APP_ENV=production
LOG_LEVEL=INFO
RATE_LIMIT_MAX_CALLS=120
RATE_LIMIT_WINDOW_SECONDS=60
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
TRANSLATION_CACHE_TTL_SECONDS=600
OPENAI_RETRY_MAX_ATTEMPTS=3
OPENAI_RETRY_INITIAL_DELAY=0.5
SECURITY_CSP="default-src 'self'; frame-ancestors 'none'; object-src 'none';"
```

## 📝 Примечания

- Используется `gpt-4.1-nano` для перевода (компактная и быстрая).
- Redis включён по умолчанию в Docker Compose; при недоступности сервис автоматически откатывается к in-memory реализациям.
- PEM-ключи загружайте из Secret Manager (Vault, AWS Secrets Manager) или монтируйте через Docker secrets; не храните ключи в репозитории.
- Endpoint `/realtime/token` пока возвращает `501` до внедрения Realtime API.

---

**Последнее обновление:** 19 октября 2025 г.
