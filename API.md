# API Документация

## Содержание
1. [Обзор](#обзор)
2. [Аутентификация](#аутентификация)
3. [REST Endpoints](#rest-endpoints)
4. [Streaming (SSE)](#streaming-sse)
5. [Ошибки](#ошибки)
6. [Примеры использования](#примеры-использования)

## Обзор

### Base URL
- **Local:** `http://localhost:8000`
- **Production:** `https://your-domain.com`

### API Версия
- Текущая версия: **v1 (OpenAI-First)**

### Поддерживаемые языки
- `ru` — Русский
- `en` — Английский
- `de` — Немецкий

## Аутентификация

Все endpoints (кроме `/healthz` и `/metrics`) требуют JWT bearer token.

### Получить токен

**Endpoint:** `POST /auth/token`

**Request:**
```bash
curl -X POST "http://localhost:8000/auth/token?user_id=demo-user"
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Использовать токен

Добавить в заголовок всех запросов:
```
Authorization: Bearer <access_token>
```

### Ошибки аутентификации
- `401 Unauthorized` — Токен отсутствует или невалиден
- `403 Forbidden` — Токен истек

## REST Endpoints

### GET /healthz

Проверка здоровья сервиса (аутентификация не требуется).

**Request:**
```bash
curl http://localhost:8000/healthz
```

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

### GET /metrics

Prometheus метрики (аутентификация не требуется).

**Request:**
```bash
curl http://localhost:8000/metrics
```

**Response (200 OK):**
```
# HELP translation_requests_total Total translation requests
# TYPE translation_requests_total counter
translation_requests_total{status="success"} 42
...
```

### POST /translate

Синхронный перевод текста.

**Request:**
```bash
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Привет, мир!",
    "source_lang": "ru",
    "target_lang": "en"
  }'
```

**Request Body Schema:**
```typescript
{
  text: string;          // 1-4000 символов
  source_lang: string;   // "ru" | "en" | "de"
  target_lang: string;   // "ru" | "en" | "de"
}
```

**Response (200 OK):**
```json
{
  "translated_text": "Hello, world!"
}
```

**Ошибки:**
- `400 Bad Request` — Некорректные параметры
- `401 Unauthorized` — Токен отсутствует/невалиден
- `429 Too Many Requests` — Rate limit превышен
- `500 Internal Server Error` — Ошибка перевода

### POST /translate/stream

Streaming перевод через Server-Sent Events.

**Request:**
```bash
curl -X POST http://localhost:8000/translate/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "ru"
  }'
```

**Request Body Schema:**
```typescript
{
  text: string;
  source_lang: string;
  target_lang: string;
}
```

**Response (200 OK):**
```
event: translation_start
data: {}

data: Привет

data:  мир

event: translation_complete
data: {}
```

**SSE Event Types:**
- `translation_start` — Начало перевода
- `data` — Фрагмент перевода (текст)
- `translation_complete` — Перевод завершен

## Streaming (SSE)

### Подключение

```typescript
const API_URL = "http://localhost:8000";
const token = "your-token-here";

async function* translateStream(
  text: string,
  targetLang: string
): AsyncGenerator<string> {
  const response = await fetch(`${API_URL}/translate/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      "Accept": "text/event-stream",
    },
    body: JSON.stringify({
      text,
      source_lang: "auto",
      target_lang: targetLang,
    }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data) yield data;
      }
    }
  }
}

// Usage
for await (const chunk of translateStream("Hello", "ru")) {
  console.log(chunk); // "Привет"
}
```

### Python пример

```python
import requests
import sseclient

url = "http://localhost:8000/translate/stream"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
data = {
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "ru",
}

response = requests.post(url, headers=headers, json=data, stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    if event.event == "translation_start":
        print("Translation started")
    elif event.data:
        print(event.data, end="", flush=True)
    elif event.event == "translation_complete":
        print("\nTranslation complete")
```

## Ошибки

### HTTP Status Codes

| Код | Описание |
|-----|----------|
| 200 | Success |
| 400 | Bad Request — Некорректные параметры |
| 401 | Unauthorized — Токен отсутствует/невалиден |
| 403 | Forbidden — Токен истек |
| 429 | Too Many Requests — Rate limit |
| 500 | Internal Server Error — Ошибка сервера |
| 503 | Service Unavailable — Сервис недоступен |

### Error Response Format

```json
{
  "detail": "Error message"
}
```

### Примеры ошибок

**400 Bad Request:**
```json
{
  "detail": [
    {
      "loc": ["body", "text"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**401 Unauthorized:**
```json
{
  "detail": "Could not validate credentials"
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

## Примеры использования

### JavaScript/TypeScript

```typescript
const API_URL = "http://localhost:8000";

// Получить токен
async function getToken(): Promise<string> {
  const response = await fetch(`${API_URL}/auth/token?user_id=demo-user`, {
    method: "POST",
  });
  const data = await response.json();
  return data.access_token;
}

// Синхронный перевод
async function translate(text: string, targetLang: string): Promise<string> {
  const token = await getToken();

  const response = await fetch(`${API_URL}/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({
      text,
      source_lang: "auto",
      target_lang: targetLang,
    }),
  });

  if (!response.ok) {
    throw new Error(`Translation failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.translated_text;
}

// Usage
const translated = await translate("Hello world", "ru");
console.log(translated); // "Привет, мир"
```

### Python

```python
import requests

API_URL = "http://localhost:8000"

# Получить токен
def get_token(user_id: str = "demo-user") -> str:
    response = requests.post(f"{API_URL}/auth/token?user_id={user_id}")
    return response.json()["access_token"]

# Синхронный перевод
def translate(text: str, target_lang: str) -> str:
    token = get_token()

    response = requests.post(
        f"{API_URL}/translate",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "source_lang": "auto",
            "target_lang": target_lang,
        },
    )

    response.raise_for_status()
    return response.json()["translated_text"]

# Usage
translated = translate("Hello world", "ru")
print(translated)  # "Привет, мир"
```

### cURL

```bash
# Получить токен
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?user_id=demo-user" | jq -r '.access_token')

# Синхронный перевод
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "ru"
  }'

# Streaming перевод
curl -X POST http://localhost:8000/translate/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "ru"
  }'
```

## Rate Limiting

**Лимиты (по умолчанию):**
- 120 запросов в минуту на пользователя
- Лимит применяется на основе user_id из JWT токена

**Response Headers:**
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1634567890
```

**При превышении лимита:**
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

## Best Practices

1. **Кеширование токенов** — Не запрашивайте новый токен для каждого запроса
2. **Обработка ошибок** — Всегда проверяйте статус ответа
3. **Rate limiting** — Реализуйте exponential backoff при 429 ответах
4. **Timeouts** — Устанавливайте разумные таймауты (30s для sync, 60s для streaming)
5. **Streaming** — Используйте streaming для больших текстов (>500 символов)

---

**Последнее обновление:** 19 октября 2025 г.
**Версия:** 1.0.0 (OpenAI-First)
