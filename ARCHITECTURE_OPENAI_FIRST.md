# OpenAI-First Архитектура — Упрощенная версия

## 🎯 Философия

**Максимум OpenAI SDK, минимум кода.**

Весь AI функционал делегируется официальным OpenAI фреймворкам:
- **Responses API** — текст → текст с streaming
- **Realtime API** — браузер ↔ модель для голоса
- Backend = тонкий шлюз (auth, rate limit, metrics)

## 🏗️ Упрощенная архитектура

```
┌─────────────────────────────────────────────────┐
│               Frontend (Next.js)                │
│  ┌──────────────┐                               │
│  │ Text UI      │                               │
│  │ (SSE client) │                               │
│  └──────┬───────┘                               │
└─────────┼───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│          Backend (FastAPI - тонкий шлюз)        │
│  ┌───────────┐      ┌──────────┐               │
│  │ POST      │      │ GET      │               │
│  │ /translate│      │ /metrics │               │
│  │ /stream   │      │ /healthz │               │
│  └─────┬─────┘      └────┬─────┘               │
│        │                 │                      │
│   ┌────▼──────────────┐  │                      │
│   │ Auth + Rate Limit │  │                      │
│   │ (JWT, Redis)      │  │                      │
│   └────┬──────────────┘  │                      │
└────────┼─────────────────┼──────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────┐
│             OpenAI Platform                     │
│  ┌──────────────┐                              │
│  │ Responses API│                              │
│  │ (gpt-4.1-nano)│                             │
│  └──────────────┘                              │
└─────────────────────────────────────────────────┘
```

## 📦 Компоненты

### Backend (FastAPI)

**Файлы (минимум):**
```
backend/
├── app/
│   ├── main.py              # FastAPI app + routes
│   ├── auth.py              # JWT + rate limiting
│   ├── translate.py         # Responses API wrapper
│   └── config.py            # Settings
├── pyproject.toml           # Dependencies
└── .env.example
```

**Dependencies (только необходимое):**
- `fastapi`
- `uvicorn[standard]`
- `openai` (официальный SDK)
- `redis` (опционально для rate limit)
- `pydantic`
- `prometheus-client`
- `pyjwt`

### Frontend (Next.js)

**Файлы (минимум):**
```
frontend/
├── app/
│   └── page.tsx             # Главная
├── lib/
│   └── api.ts               # API client
├── package.json
└── .env.local.example
```

**Dependencies (минимум):**
- `next`
- `react`
- Tailwind CSS (опционально)

## 🔄 Поток данных

### 1. Текстовый перевод (SSE)

```
User → Frontend → POST /translate (SSE)
                    ↓
                 Backend (auth + rate limit)
                    ↓
                 OpenAI Responses API
                    ↓ (streaming)
                 Backend → Frontend → User
```

**Backend код (упрощенный):**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

client = AsyncOpenAI()
app = FastAPI()

@app.post("/translate/stream")
async def translate_stream(text: str, target_lang: str):
    async def sse():
        stream = await client.responses.stream(
            model="gpt-4.1-nano",
            input=[
                {"role": "system", "content": f"Translate to {target_lang}"},
                {"role": "user", "content": text},
            ],
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield f"data: {event.delta}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
```

### 2. Голосовой перевод (Realtime, запланировано)

- Endpoint `/realtime/token` выдает эфемерный токен OpenAI.
- Браузер устанавливает WebRTC-сессию с Realtime API напрямую.
- UI отображает субтитры и воспроизводит синтезированный голос.

Функциональность включается после стабилизации Realtime API и прохождения QA.

## 🔐 Безопасность (упрощенная)

### JWT для API

```python
# auth.py
import jwt
from datetime import datetime, timedelta

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

### Rate Limiting (опционально с Redis)

```python
# Простой in-memory для dev
rate_limits = {}

def check_rate_limit(key: str, max_calls: int = 60):
    now = time.time()
    if key not in rate_limits:
        rate_limits[key] = []

    # Очистить старые
    rate_limits[key] = [t for t in rate_limits[key] if now - t < 60]

    if len(rate_limits[key]) >= max_calls:
        raise HTTPException(429, "Rate limit exceeded")

    rate_limits[key].append(now)
```

## 📊 Метрики (минимальные)

```python
from prometheus_client import Counter, Histogram, make_asgi_app

translation_counter = Counter("translations_total", "Total translations")
latency_histogram = Histogram("translation_latency_seconds", "Latency")

@app.post("/translate")
async def translate(text: str):
    translation_counter.inc()
    with latency_histogram.time():
        # Перевод
        pass

# Expose metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

## 🚀 Развертывание

### Docker Compose (упрощенный)

```yaml
version: '3.9'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
```

## ✅ Преимущества OpenAI-First

1. **Минимальный код** — только то, что необходимо для auth, rate limit и метрик.
2. **Единый SDK** — Responses API покрывает синхронный и потоковый сценарии.
3. **Потоковый UX** — нативный SSE без кастомных брокеров.
4. **Простая инфраструктура** — достаточно Docker Compose и Prometheus-совместимых метрик.
5. **Расширяемость** — Realtime API подключается без переработки существующего слоя.

## 🎯 Следующие шаги

1. Перейти на `AsyncOpenAI` / Responses API в коде backend.
2. Добавить Redis для rate limiting и кэша в production.
3. Реализовать Realtime API с эфемерными токенами и голосовым UI.
4. Расширить тестовое покрытие и автоматизировать деплой.

---

**Последнее обновление:** 19 октября 2025 г.
