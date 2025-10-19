# Frontend - OpenAI-First Approach

Минимальный Next.js frontend для трехязычного переводчика.

## 🎯 Философия

- **Минимум зависимостей** — только Next.js + React + Tailwind
- **Нативный fetch** — без axios/query библиотек
- **SSE streaming** — нативный ReadableStream
- **Простота** — ~200 строк кода

## 📦 Структура

```
frontend/
├── app/
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Главная страница (~150 LoC)
│   └── globals.css          # Tailwind styles
├── lib/
│   └── api.ts               # API client (~100 LoC)
├── package.json             # Dependencies (3 core packages)
├── Dockerfile
└── README.md
```

## 🚀 Быстрый старт

### Требования

- Node.js 20 LTS (см. `.nvmrc` / `.node-version`)
- npm 10+

### 1. Установка

```bash
cd frontend
nvm use 20.18.0  # если используете nvm
npm install
```

### 2. Конфигурация

```bash
cp .env.local.example .env.local
# Настроить NEXT_PUBLIC_API_URL
```

### 3. Запуск

```bash
npm run dev
```

Открыть http://localhost:3000

## 🔧 Возможности

- ✅ JWT аутентификация
- ✅ SSE streaming перевод
- ✅ Автоопределение языка
- ✅ Выбор целевого языка (RU, EN, DE)
- ✅ Responsive UI
- ✅ Error handling

## 📦 Зависимости (только 3!)

1. **next** — Framework
2. **react** — UI library
3. **react-dom** — DOM bindings

## 🎨 Styling

Tailwind CSS для минимального размера bundle:

- Utility-first CSS
- Purged в production
- No runtime overhead

## 🏗️ Build

```bash
# Development
npm run dev

# Production build
npm run build
npm start

# Lint
npm run lint

# Unit tests
npm test
```

## 📊 Метрики

- **Bundle size:** ~200 KB (gzipped)
- **Lines of code:** ~200
- **Dependencies:** 3 (без dev)
- **Load time:** <1s

## 🚀 Production

### Docker

```bash
docker build -t translator-frontend .
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=https://api.example.com \
  translator-frontend
```

### Vercel

```bash
vercel deploy
```

## 🔒 Безопасность

- No secrets на frontend
- Auth token получается через backend
- CORS настроен на backend
- Input validation

---

**Последнее обновление:** 19 октября 2025 г.
