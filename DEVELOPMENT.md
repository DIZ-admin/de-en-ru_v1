# Гайд для разработчиков

## Содержание
1. [Структура проекта](#структура-проекта)
2. [Рабочий процесс](#рабочий-процесс)
3. [Кодовые стандарты](#кодовые-стандарты)
4. [Backend разработка](#backend-разработка)
5. [Frontend разработка](#frontend-разработка)
6. [Тестирование](#тестирование)
7. [Debugging](#debugging)

## Структура проекта

```
de-en-ru/
├── backend/                    # FastAPI приложение (~500 LoC)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic settings
│   │   ├── auth.py            # JWT authentication
│   │   ├── translate.py       # OpenAI Responses API
│   │   └── main.py            # FastAPI app + endpoints
│   ├── tests/                 # pytest тесты (async, Redis, OpenAI stubs)
│   ├── pyproject.toml         # 7 dependencies only
│   ├── Dockerfile
│   ├── .env.example
│   └── README.md
├── frontend/                   # Next.js приложение (~270 LoC)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           # Main translation UI
│   │   └── globals.css
│   ├── lib/
│   │   ├── api.ts             # API client (native fetch)
│   │   └── sse.ts             # SSE streaming utilities + tests
│   ├── package.json           # 3 dependencies only
│   ├── Dockerfile
│   ├── .env.local.example
│   └── README.md
├── docker-compose.yml
├── .gitignore
├── README.md
├── SETUP.md
├── DEVELOPMENT.md (этот файл)
├── API.md
├── ARCHITECTURE_OPENAI_FIRST.md
└── REFACTORING_SUMMARY.md
```

## Рабочий процесс

### 1. Создать feature branch

```bash
git checkout -b feature/my-feature
# или для bug fixes:
git checkout -b fix/bug-description
```

### 2. Делать коммиты

```bash
git add .
git commit -m "feat: add translation feature"
# или
git commit -m "fix: resolve streaming issue"
```

Формат коммитов: [Conventional Commits](https://www.conventionalcommits.org/)
- `feat:` — новая функциональность
- `fix:` — исправление бага
- `docs:` — изменения в документации
- `refactor:` — рефакторинг без изменения API
- `test:` — добавление тестов

### 3. Запушить и создать Pull Request

```bash
git push origin feature/my-feature
# Затем создать PR через GitHub UI
```

## Кодовые стандарты

### Backend (Python)

**Форматирование:**
```bash
# Black (форматирование)
poetry run black app/

# Ruff (linting)
poetry run ruff check app/ --fix

# Type checking (если настроен mypy)
poetry run mypy app/
```

**Type hints:**
```python
from typing import AsyncIterator

async def translate_text_stream(
    text: str,
    target_lang: str
) -> AsyncIterator[str]:
    """Stream translation chunks from OpenAI."""
    pass
```

**Docstrings (Google style):**
```python
def create_access_token(user_id: str) -> dict[str, str | int]:
    """Create JWT access token.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with access_token, token_type, expires_in

    Raises:
        ValueError: If user_id is empty
    """
    pass
```

**Структура:**
- Максимум 300 строк на файл (цель простоты)
- Группировать импорты: stdlib → third-party → local
- Использовать абсолютные импорты

### Frontend (TypeScript)

**Форматирование:**
```bash
# Prettier
npm run format

# ESLint
npm run lint -- --fix
```

**Naming conventions:**
- Components: PascalCase (`TranslationPanel.tsx`)
- Hooks: camelCase (`useTranslation.ts`)
- Utils: camelCase (`formatText.ts`)
- Constants: UPPER_SNAKE_CASE (`API_BASE_URL`)

**React Best Practices:**
```typescript
"use client";

import { useState } from "react";

interface TranslationPanelProps {
  onTranslate: (text: string) => void;
  isLoading?: boolean;
}

export default function TranslationPanel({
  onTranslate,
  isLoading = false,
}: TranslationPanelProps) {
  const [text, setText] = useState("");

  return (
    <div className="space-y-4">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full p-4 border rounded"
      />
      <button
        onClick={() => onTranslate(text)}
        disabled={isLoading || !text.trim()}
        className="px-4 py-2 bg-blue-500 text-white rounded"
      >
        {isLoading ? "Translating..." : "Translate"}
      </button>
    </div>
  );
}
```

## Backend разработка

### Структура backend/app/

Ключевые файлы backend:
- `config.py` — pydantic settings, RS256/Redis/security конфигурации.
- `auth.py` — JWT (создание, валидация, rate limiting, retry-safe логика).
- `translate.py` — OpenAI Responses API c backoff и кэшированием.
- `security.py` — дополнительные HTTP-заголовки.
- `main.py` — FastAPI, Prometheus, health-check.

### RS256 ключи и переменные

```bash
# Локальная генерация
openssl genrsa -out secrets/private.pem 2048
openssl rsa -in secrets/private.pem -pubout -out secrets/public.pem

# Пример .env (dev)
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=./secrets/private.pem
JWT_PUBLIC_KEY_PATH=./secrets/public.pem
JWT_ADDITIONAL_PUBLIC_KEYS=
JWT_KID=dev-key
```

- В production ключи подгружаются из Secret Manager (Vault, AWS Secrets Manager, 1Password) и **никогда** не коммитятся в git.
- Для ротации добавьте предыдущие публичные ключи в `JWT_ADDITIONAL_PUBLIC_KEYS` (разделитель `||`) или `JWT_ADDITIONAL_PUBLIC_KEYS_PATHS`.

### Adding a new endpoint

1. **Добавить модель в main.py:**
```python
class NewRequest(BaseModel):
    field: str
```

2. **Создать endpoint:**
```python
@app.post("/new-endpoint")
async def new_endpoint(request: NewRequest):
    # Ваша логика
    return {"result": "success"}
```

### Using logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Translation started", extra={
    "text_length": len(text),
    "target_lang": target_lang
})

logger.error("Translation failed", exc_info=True)
```

### Testing backend (TODO)

```python
# tests/test_translate.py
import pytest
from app.translate import translate_text

@pytest.mark.asyncio
async def test_translate_text():
    result = await translate_text("Hello", "ru")
    assert result
    assert isinstance(result, str)
```

## Frontend разработка

### Структура frontend/

```typescript
// app/page.tsx - Main page
"use client";

import { useState } from "react";
import { translateText } from "@/lib/api";

export default function Home() {
  const [text, setText] = useState("");
  const [result, setResult] = useState("");

  const handleTranslate = async () => {
    const translated = await translateText(text, "ru");
    setResult(translated);
  };

  return <div>{/* UI */}</div>;
}


// lib/api.ts - API client
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function translateText(text: string, targetLang: string) {
  const response = await fetch(`${API_URL}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_lang: targetLang })
  });

  if (!response.ok) {
    throw new Error(`Translation failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.translated_text;
}
```

### Using Server-Sent Events (SSE)

```typescript
export async function* translateTextStream(
  text: string,
  targetLang: string,
  token: string
): AsyncGenerator<string> {
  const response = await fetch(`${API_URL}/translate/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({ text, target_lang: targetLang }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        yield data;
      }
    }
  }
}
```

## Тестирование

### Backend (pytest + asyncio)

```bash
cd backend

# Все тесты (используется poetry, покрытие ≥80%)
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Запустить конкретный файл
poetry run pytest tests/test_translate.py
```

Основные сценарии: кэширование переводов (Redis + fallback), rate limiting, mock Responses API.

### Frontend (Vitest / Playwright)

```bash
cd frontend

# Unit тесты (Vitest + coverage v8)
npm test

# E2E (Playwright, требуется `npx playwright install`)
npm run test:e2e
```

## Debugging

### Backend debugging

**Логирование:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.debug("Variable value: %s", variable)
```

**VSCode launch config** (`.vscode/launch.json`):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "justMyCode": true
    }
  ]
}
```

### Frontend debugging

**Browser DevTools:**
- `F12` — открыть DevTools
- `Console` — просмотр логов и ошибок
- `Network` — проверка API запросов

**Next.js debugging:**
```bash
# Development mode с подробными логами
DEBUG=* npm run dev

# Просмотр build
npm run build
npm start
```

## Полезные команды

### Docker

```bash
# Перестроить контейнер
docker-compose build backend

# Перезапустить сервис
docker-compose restart backend

# Просмотр логов
docker-compose logs -f backend

# Зайти в контейнер
docker-compose exec backend sh
```

### Git

```bash
# Просмотреть изменения
git status
git diff

# Stash изменения
git stash
git stash pop

# Отменить последний коммит (сохранив изменения)
git reset --soft HEAD~1
```

### Python

```bash
# Активировать venv
source venv/bin/activate

# Обновить зависимости
poetry update

# Добавить новую зависимость
poetry add package-name

# Экспортировать requirements.txt
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

### Node

```bash
# Обновить зависимости
npm update

# Добавить зависимость
npm install package-name

# Очистить cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

## Архитектурные решения

### Почему OpenAI-First?

1. **Простота** — Минимум кода, легко поддерживать
2. **Надежность** — Используем проверенные инструменты (OpenAI SDK)
3. **Скорость разработки** — MVP готов за часы, а не недели
4. **Меньше зависимостей** — Меньше точек отказа

См. подробнее в [ARCHITECTURE_OPENAI_FIRST.md](./ARCHITECTURE_OPENAI_FIRST.md)

### Что можно улучшить

1. **Redis** — Для продакшн-кеширования и rate limiting
2. **Тестирование** — Добавить pytest и Playwright тесты
3. **Мониторинг** — Настроить Grafana дашборды для Prometheus метрик
4. **CI/CD** — Автоматизировать деплой через GitHub Actions

См. список задач в Archon MCP.

---

**Последнее обновление:** 19 октября 2025 г.
**Версия:** 1.0.0 (OpenAI-First)
