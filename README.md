# Real-Time Trilingual Translator (RU-EN-DE)

**Версия:** 1.0.0 (OpenAI-First)
**Статус:** ✅ MVP готов к запуску

## 🎯 Обзор

Real-Time Trilingual Translator — **минималистичная** система потокового перевода между русским, английским и немецким языками. Проект создан по принципу **OpenAI-First**:
- **Backend:** FastAPI + OpenAI SDK (~500 LoC, 7 зависимостей)
- **Frontend:** Next.js 14 + React 18 (~270 LoC, 3 зависимости)

### 🎨 Философия OpenAI-First

**Максимум OpenAI SDK, минимум кода.**

Весь AI функционал делегируется официальному OpenAI SDK:
- **Responses API** для текстового перевода
- **Нативный SSE** для streaming
- Backend = тонкий шлюз (auth, rate limit, metrics)

## ✨ Основные возможности

- ✅ **Потоковый перевод** через OpenAI Responses API (SSE)
- ✅ **Синхронный REST API** для быстрого перевода
- ✅ **Прямой вызов OpenAI** без абстракций
- ✅ **Минимальный код** — 500 строк backend, 270 строк frontend
- ✅ **Кэширование переводов** (in-memory для MVP)
- ✅ **Rate limiting** и защита от DoS
- ✅ **JWT аутентификация**
- ✅ **Prometheus метрики**
- ✅ **Мониторинг** (Prometheus + Grafana) и алёрты по ключевым метрикам
- ✅ **Security headers** (CSP, HSTS), RS256 и key rotation
- 🗣️ **Планируется голосовой ввод** — архитектура автоопределения языка описана в [VOICE_INPUT_DESIGN.md](./VOICE_INPUT_DESIGN.md)

## 🚀 Быстрый старт

### Локальная разработка (Docker Compose)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/DIZ-admin/de-en-ru.git
cd de-en-ru

# 2. Создать .env файлы
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# 3. Добавить OpenAI API ключ в backend/.env
# Отредактируйте файл и добавьте: OPENAI_API_KEY=sk-...

# 4. Запустить через Docker Compose
docker-compose up -d

# 5. Проверить статус
curl http://localhost:8000/healthz
open http://localhost:3000
# Prometheus и Grafana (по умолчанию):
# http://localhost:9090  (Prometheus)
# http://localhost:3001  (Grafana, admin/admin)
```

### Ручная установка (без Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install poetry
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Redis (macOS):**
```bash
brew install redis
brew services start redis
```

## 📚 Документация

### 🔥 Важнейшие документы (читать первыми!)

| Документ | Описание |
|----------|---------|
| **[ARCHITECTURE_OPENAI_FIRST.md](./ARCHITECTURE_OPENAI_FIRST.md)** | 🔥 OpenAI-First архитектура (читать первым!) |
| **[REFACTORING_SUMMARY.md](./REFACTORING_SUMMARY.md)** | 🔥 Результаты рефакторинга и метрики |

### 📖 Детальная документация

| Документ | Описание |
|----------|---------|
| [SETUP.md](./SETUP.md) | Подробные инструкции по установке и настройке |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | Гайд для разработчиков, работа с кодом |
| [API.md](./API.md) | Полная документация REST API и SSE |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Инструкции по развертыванию |
| [SECURITY.md](./SECURITY.md) | Документация по безопасности |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Рекомендации для контрибьюторов |
| [VOICE_INPUT_DESIGN.md](./VOICE_INPUT_DESIGN.md) | Архитектура голосового ввода и автоопределения языка |

## 🏗️ Архитектура

### Компоненты

```
Frontend (Next.js)                Backend (FastAPI)
├── текстовый интерфейс          ├── /translate (REST)
├── потоковый клиент SSE         ├── /translate/stream (SSE)
└── измерение латентности        ├── /realtime/token (заглушка до релиза)
                                  ├── аутентификация (JWT)
                                  ├── rate limiting
                                  └── метрики (/metrics, /healthz)

                     ↓

             OpenAI Responses API
             Redis (опционально)
```

### Поток данных

1. Пользователь вводит текст в интерфейсе.
2. Фронтенд получает JWT (`/auth/token`) и отправляет запрос на backend.
3. Backend проверяет лимиты, читает кэш, при необходимости обращается к OpenAI Responses API.
4. Ответ стримится обратно через SSE; фронтенд постепенно отображает перевод.

## 🔧 Технологический стек

### Backend
- Python 3.11
- FastAPI 0.111
- OpenAI SDK 1.40
- Pydantic / pydantic-settings
- PyJWT
- Prometheus-client
- (опционально) Redis 5+

### Frontend
- TypeScript 5.4
- Next.js 14.2 (App Router)
- React 18.3
- Tailwind CSS

### Инфраструктура
- Docker + Docker Compose
- Prometheus совместимые метрики
- Redis (кэш + rate limit), Prometheus, Grafana, Redis Exporter

## 🛠️ Операционные инструменты

- **Redis** — production-кэш и rate limiting (в dev включается через `REDIS_ENABLED=true`).
- **Prometheus** — собирает метрики `/metrics`, использует правила из `monitoring/alerting_rules.yml`.
- **Grafana** — автоматическая провизия датасорсов и дашборда `Translator Overview`.
- **Redis Exporter** — экспорт базовых метрик Redis (порт `9121`).
- **Alerting** — пример rules-файла с триггерами по доступности, латентности и rate limit.
## 🔐 Безопасность

- JWT-аутентификация (HS256, планируется миграция на RS256).
- In-memory rate limiting (Redis для продакшена).
- Валидация входных данных через Pydantic.
- Дополнительные рекомендации смотрите в [SECURITY.md](./SECURITY.md).

## 📊 Мониторинг

- `GET /healthz` — health-check.
- `GET /metrics` — Prometheus метрики (`translations_total`, `translation_latency_seconds`, `translation_counter` по статусам).

## 📝 Переменные окружения

### Backend
```bash
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
RATE_LIMIT_MAX_CALLS=120
RATE_LIMIT_WINDOW_SECONDS=60
APP_ENV=development
LOG_LEVEL=INFO
ALLOWED_ORIGINS=["http://localhost:3000"]
# Redis_* переменные используются при подключении внешнего кэша
```

### Frontend
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🧪 Тестирование

```bash
# Backend (Poetry)
cd backend
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Frontend (Vitest + coverage)
cd frontend
npm test

# Playwright E2E (предварительно: npx playwright install)
npm run test:e2e
```

## 📦 Структура проекта

```
de-en-ru/
├── backend/
│   ├── app/
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── main.py
│   │   └── translate.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── lib/
│   │   ├── api.ts
│   │   └── sse.ts
│   ├── tests/
│   │   └── e2e/translate.spec.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── setupTests.ts
│   └── package.json
├── monitoring/
│   ├── grafana/
│   └── prometheus.yml
├── CODEx_PROJECT_VISION.md
├── CODEx_PRD.md
├── docker-compose.yml
└── README.md
```

## 🎓 Примеры запросов

```bash
# Получить токен
curl -X POST "http://localhost:8000/auth/token?user_id=demo-user"

# Синхронный перевод
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"Привет, мир!","source_lang":"ru","target_lang":"en"}'

# Потоковый перевод (SSE)
curl -X POST http://localhost:8000/translate/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"text":"Это длинный текст...","target_lang":"de"}'
```

## 🤝 Контрибьюция

Смотрите [CONTRIBUTING.md](./CONTRIBUTING.md) для деталей о:
- Процессе создания Pull Request
- Стандартах кода
- Процессе ревью

## 📄 Лицензия

Смотрите LICENSE файл для деталей.

## 📞 Контакты

- GitHub: https://github.com/DIZ-admin/de-en-ru
- Issues: https://github.com/DIZ-admin/de-en-ru/issues

---

**Последнее обновление:** 19 октября 2025 г.
