# Инструкции по установке и настройке

## Содержание
1. [Требования](#требования)
2. [Локальная разработка с Docker](#локальная-разработка-с-docker)
3. [Ручная установка](#ручная-установка-без-docker)
4. [Настройка переменных окружения](#настройка-переменных-окружения)
5. [Проверка установки](#проверка-установки)
6. [Решение проблем](#решение-проблем)

## Требования

### Системные требования
- **ОС:** macOS, Linux, Windows (WSL2)
- **Docker:** 24.0+ (для Docker-based setup)
- **Docker Compose:** 2.0+ (для Docker-based setup)

### Для ручной установки
- **Node.js:** 20 LTS (рекомендуемая версия в `.nvmrc`)
- **Python:** 3.11+
- **Poetry:** 1.7+

### Учетные данные
- **OpenAI API Key:** Получить на https://platform.openai.com/api-keys

## Локальная разработка с Docker

### Быстрый старт

**1. Клонировать репозиторий**
```bash
git clone https://github.com/your-org/de-en-ru.git
cd de-en-ru
```

**2. Создать файл конфигурации backend**
```bash
# Скопировать пример
cp backend/.env.example backend/.env

# Отредактировать и добавить OpenAI API ключ
# backend/.env:
OPENAI_API_KEY=sk-your-key-here
```

**3. Создать файл конфигурации frontend (опционально)**
```bash
# Frontend работает с дефолтными настройками, но можно кастомизировать
cp frontend/.env.local.example frontend/.env.local
```

**4. Запустить все сервисы**
```bash
docker-compose up -d
```

**5. Проверить статус**
```bash
# Проверить здоровье backend
curl http://localhost:8000/healthz

# Открыть приложение в браузере
open http://localhost:3000  # macOS
```

**6. Просмотр логов**
```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f frontend
```

**7. Остановить все сервисы**
```bash
docker-compose down
```

## Ручная установка (без Docker)

### Backend установка

**1. Перейти в директорию backend**
```bash
cd backend
```

**2. Создать виртуальное окружение**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows
```

**3. Установить Poetry и зависимости**
```bash
pip install poetry
poetry install --no-root
```

**4. Создать .env файл**
```bash
cp .env.example .env
# Отредактируйте .env и добавьте OPENAI_API_KEY
```

**5. Запустить backend сервер**
```bash
poetry run uvicorn app.main:app --reload --port 8000
```

Backend должен быть доступен на `http://localhost:8000`

### Frontend установка

**1. Перейти в директорию frontend**
```bash
cd frontend
```

**2. Установить зависимости**
```bash
npm install
```

**3. Запустить dev сервер**
```bash
npm run dev
```

Frontend должен быть доступен на `http://localhost:3000`

## Настройка переменных окружения

### Backend переменные (.env)

**Минимальная конфигурация:**
```bash
# ========== OpenAI (REQUIRED) ==========
OPENAI_API_KEY=sk-your-key-here

# ========== JWT Authentication ==========
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Дополнительные настройки:**
```bash
# ========== Application ==========
DEFAULT_MODEL=gpt-4.1-nano
MAX_TEXT_LENGTH=4000
LOG_LEVEL=INFO

# ========== Rate Limiting (in-memory) ==========
RATE_LIMIT_MAX_CALLS=120
RATE_LIMIT_WINDOW_SECONDS=60
```

### Frontend переменные (.env.local)

**Опционально** (дефолтные значения работают для локальной разработки):
```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Проверка установки

### 1. Проверить здоровье backend
```bash
curl http://localhost:8000/healthz
```

Ожидаемый ответ:
```json
{
  "status": "healthy"
}
```

### 2. Проверить метрики Prometheus
```bash
curl http://localhost:8000/metrics
```

### 3. Получить JWT токен
```bash
curl -X POST http://localhost:8000/auth/token?user_id=demo-user
```

### 4. Попробовать перевод
```bash
# Сохранить токен
TOKEN="your-token-from-previous-step"

# Синхронный перевод
curl -X POST http://localhost:8000/translate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "ru"
  }'
```

### 5. Проверить frontend
Откройте `http://localhost:3000` в браузере и попробуйте перевести текст.

## Решение проблем

### Port уже занят
```bash
# Найти процесс, использующий порт
lsof -i :8000  # Backend
lsof -i :3000  # Frontend

# Завершить процесс
kill -9 <PID>
```

### OpenAI API ошибка: "Invalid API Key"
```bash
# Проверить, что ключ корректно установлен
cat backend/.env | grep OPENAI_API_KEY

# Убедиться, что нет лишних пробелов
# OPENAI_API_KEY=sk-... (правильно)
# OPENAI_API_KEY= sk-... (неправильно - пробел после =)
```

### Docker проблемы

```bash
# Перестроить образы
docker-compose build --no-cache

# Удалить все и начать заново
docker-compose down -v
docker-compose up -d

# Проверить логи
docker-compose logs -f
```

### Frontend не подключается к Backend

```bash
# Убедиться, что backend работает
curl http://localhost:8000/healthz

# Проверить URL в браузерной консоли
# Откройте DevTools (F12) → Network → посмотрите failed requests

# Для локальной разработки backend должен быть на localhost:8000
```

### Python/Node версия не соответствует

```bash
# Проверить версии
python --version  # Должен быть 3.11+
node --version    # Должен быть 20.x (nvm use)

# Обновить через pyenv/nvm
pyenv install 3.11
nvm install 20.18.0
nvm use 20.18.0
```

## Дополнительные команды

### Backend

```bash
cd backend

# Форматировать код
poetry run black app/

# Линтинг
poetry run ruff check app/

# Type checking
poetry run mypy app/
```

### Frontend

```bash
cd frontend

# Build для production
npm run build

# Lint
npm run lint

# Format
npm run format
```

## Следующие шаги

1. Прочитайте [ARCHITECTURE_OPENAI_FIRST.md](./ARCHITECTURE_OPENAI_FIRST.md) для понимания архитектуры
2. Ознакомьтесь с [API.md](./API.md) для документации API
3. Смотрите [DEVELOPMENT.md](./DEVELOPMENT.md) для гайда по разработке

---

**Последнее обновление:** 19 октября 2025 г.
**Версия:** 1.0.0 (OpenAI-First)
