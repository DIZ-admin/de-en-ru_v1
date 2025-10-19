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
├── REFACTORING_SUMMARY.md
├── TROUBLESHOOTING.md
├── DOCUMENTATION_AUDIT_REPORT.md
└── SECURITY.md
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
## Backend разработка

### Структура backend/app/

Ключевые файлы backend:
- `config.py` — pydantic settings, RS256/Redis/security конфигурации.
- `auth.py` — JWT (создание, валидация, rate limiting, retry-safe логика).
- `translate.py` — OpenAI Responses API c backoff, кэшированием и функциями `transcribe_audio_file`/`translate_voice_text`.
- `security.py` — дополнительные HTTP-заголовки.
- `main.py` — FastAPI, Prometheus, health-check, `/voice-translate` с валидацией аудио и голосовыми метриками.

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

## Frontend разработка

### Структура frontend/

- `app/page.tsx` — основная страница: форма перевода, обработка SSE, голосовой UI (MediaRecorder, загрузка файла, отображение confidence/метрик).
- `lib/api.ts` — обёртки над REST/SSE/voice endpoint’ами (`getAuthToken`, `translateText`, `translateTextStream`, `voiceTranslate`).
- `lib/sse.ts` — универсальный декодер SSE с буферизацией.
- `tests` и `app/page.test.tsx` — Vitest-тесты (streaming, voice upload, MediaRecorder mock).

> При добавлении новых UI-компонентов сохраняем философию «тонкого клиента»: минимум состояний, весь AI-интеллект в backend.

### Using Server-Sent Events (SSE)

- Используем `lib/sse.ts` с классом `SSEDecoder`, который буферизует обрезанные `data:` строки и покрыт regression-тестами (`lib/sse.test.ts`).
- `translateTextStream` в `lib/api.ts` читает `ReadableStream`, передаёт отрезки в `SSEDecoder` и возвращает асинхронный генератор текстовых чанков.
- При ошибках соединения выбрасывается исключение с user-friendly сообщением, UI показывает алерт и предлагает повторить попытку.

> Детали реализации см. `frontend/lib/api.ts` и тесты `frontend/tests`.

## Тестирование

### Backend (pytest + asyncio)

```bash
cd backend

# Все тесты (используется poetry, покрытие ≥80%)
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Запустить конкретный файл
poetry run pytest tests/test_translate.py
```

Основные сценарии: кэш/Redis + fallback, rate limiting (включая `weight`), ошибки/таймауты OpenAI, голосовая транскрипция и перевод с моками Whisper/Responses.

### Frontend (Vitest / Playwright)

```bash
cd frontend

# Unit тесты (Vitest + coverage v8)
npm test

# Тесты голосового UI (MediaRecorder/file upload)
npm test -- app/page.test.tsx

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
