# Рекомендации для контрибьюторов

## Содержание
1. [Как начать](#как-начать)
2. [Процесс разработки](#процесс-разработки)
3. [Pull Request процесс](#pull-request-процесс)
4. [Кодовые стандарты](#кодовые-стандарты)
5. [Тестирование](#тестирование)
6. [Коммит сообщения](#коммит-сообщения)

## Как начать

### 1. Fork и clone репозиторий

```bash
# Fork на GitHub (кнопка Fork)
git clone https://github.com/YOUR-USERNAME/de-en-ru.git
cd de-en-ru

# Добавить upstream
git remote add upstream https://github.com/DIZ-admin/de-en-ru.git
```

### 2. Установить окружение

```bash
# Смотрите SETUP.md для полных инструкций
docker-compose up -d

# Или вручную
cd backend && poetry install
cd ../frontend && npm install
```

### 3. Создать feature branch

```bash
# Обновить develop
git fetch upstream
git checkout develop
git merge upstream/develop

# Создать новую ветку
git checkout -b feature/my-feature
# или для bug fixes
git checkout -b fix/issue-description
```

## Процесс разработки

### Backend разработка

1. **Создать файл с кодом** в `backend/app/`
2. **Добавить тесты** в `backend/tests/`
3. **Запустить тесты**
   ```bash
   cd backend
   pytest tests/
   ```
4. **Lint и format**
   ```bash
   black app/
   ruff check app/ --fix
   mypy app/
   ```

### Frontend разработка

1. **Создать компонент** в `frontend/components/` или `frontend/hooks/`
2. **Добавить тесты** в `frontend/tests/`
3. **Запустить тесты**
   ```bash
   cd frontend
   npm test
   ```
4. **Lint и format**
   ```bash
   npm run lint -- --fix
   npm run format
   ```

### Общие правила

- Один feature или bug fix на ветку
- Регулярно pull'ить обновления из upstream
- Обновить tests и documentation
- Следовать кодовым стандартам

## Pull Request процесс

### 1. Убедиться что код готов

```bash
# Обновить develop
git fetch upstream
git rebase upstream/develop

# Запустить все проверки
cd backend && pytest --cov=app
cd ../frontend && npm test
npm run lint
npm run format
```

### 2. Создать PR

```bash
# Push ветку
git push origin feature/my-feature
```

3. **На GitHub:**
   - Кликнуть "Compare & pull request"
   - Заполнить PR template (смотрите ниже)
   - Требовать review у минимум двух people

### PR Template

```markdown
## Description
Краткое описание изменений

## Related Issue
Fixes #123 (или)
Relates to #456

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## How Has This Been Tested?
Описание тестов

## Screenshots (если applicable)
Добавить скриншоты для UI изменений

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tested locally

## Performance Impact
- [ ] No performance impact
- [ ] Potential performance improvement
- [ ] Potential performance regression

## Security Considerations
- [ ] No security implications
- [ ] Security implications addressed

## Breaking Changes
- [ ] No breaking changes
- [ ] Breaking changes documented
```

### 3. Code Review

- Ответить на комментарии
- Запросить re-review после изменений
- Минимум 2 approvals требуется

### 4. Merge

- Требуется passing CI/CD
- Требуется все checks зелёные
- Требуется 2+ approvals

## Кодовые стандарты

### Python (Backend)

**Line length:** 88 символов (Black)

**Imports:**
```python
# 1. Standard library
import os
import sys
from typing import Dict, List, Optional

# 2. Third-party
import numpy as np
from fastapi import FastAPI, Depends
from pydantic import BaseModel

# 3. Local imports
from app.services import translate_service
from app.models import TranslateRequest
```

**Naming conventions:**
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

**Type hints (обязательно):**
```python
def translate(
    text: str,
    target_langs: List[str],
    source_lang: str = "auto"
) -> Dict[str, str]:
    """Перевести текст."""
    pass

async def async_translate(
    request: TranslateRequest,
    _=Depends(auth_check)
) -> TranslateResponse:
    """Асинхронный перевод."""
    pass
```

**Docstrings (Google style):**
```python
def create_token(user_id: str, expires_in: int = 1800) -> str:
    """
    Создать JWT токен для пользователя.

    Args:
        user_id: ID пользователя
        expires_in: Время жизни в секундах

    Returns:
        JWT токен

    Raises:
        ValueError: Если user_id пуст
    """
    pass
```

### TypeScript (Frontend)

**Line length:** 88 символов (Prettier)

**Interface naming:**
```typescript
interface UserProps {
  name: string;
  age: number;
}

type TranslationResult = Record<string, string>;

enum Language {
  RU = "ru",
  EN = "en",
  DE = "de",
}
```

**Component naming:**
```typescript
// ✅ ПРАВИЛЬНО
export const TranslatePanel: React.FC<TranslatePanelProps> = () => {};

// ❌ НЕПРАВИЛЬНО
export const translatePanel = () => {};
export function translate_panel() {}
```

**Hooks:**
```typescript
export const useTranslation = (text: string) => {
  const [result, setResult] = useState("");

  useEffect(() => {
    // Effect logic
  }, [text]);

  return result;
};
```

## Тестирование

### Backend тесты

**Требования:**
- Минимум 80% покрытие
- Unit + integration тесты
- Тестировать edge cases

**Пример:**
```python
# tests/unit/test_translate.py
import pytest
from app.agents.manager import TranslationManager

class TestTranslationManager:
    @pytest.fixture
    def manager(self):
        return TranslationManager()

    @pytest.mark.asyncio
    async def test_translate_single_language(self, manager):
        result = await manager.translate(
            text="Hello",
            target_langs=["ru"]
        )
        assert "ru" in result

    @pytest.mark.asyncio
    async def test_translate_invalid_language(self, manager):
        with pytest.raises(ValueError):
            await manager.translate(
                text="Hello",
                target_langs=["invalid"]
            )
```

**Запуск:**
```bash
pytest tests/unit/
pytest tests/integration/
pytest --cov=app --cov-report=html
```

### Frontend тесты

**Требования:**
- Минимум 80% покрытие
- Unit + component + E2E тесты

**Пример:**
```typescript
// tests/unit/hooks.test.ts
import { renderHook, act, waitFor } from "@testing-library/react";
import { useTranslation } from "hooks/useTranslation";

describe("useTranslation", () => {
  it("should translate text", async () => {
    const { result } = renderHook(() => useTranslation("Hello"));

    await waitFor(() => {
      expect(result.current).toBe("Привет");
    });
  });
});
```

**Запуск:**
```bash
npm test
npm run test:e2e
npm run test -- --coverage
```

## Коммит сообщения

### Формат

Используйте **conventional commits** формат:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Типы

- `feat` — Новая функция
- `fix` — Исправление ошибки
- `docs` — Документация
- `style` — Форматирование (не влияет на логику)
- `refactor` — Рефакторинг без изменения функциональности
- `perf` — Улучшение производительности
- `test` — Добавление или обновление тестов
- `chore` — Обновление зависимостей или build

### Примеры

```bash
# Новая функция
git commit -m "feat(translation): add streaming support for SSE"

# Bug fix
git commit -m "fix(api): handle empty text input validation"

# Документация
git commit -m "docs(api): add WebSocket endpoint examples"

# С описанием
git commit -m "feat(agents): implement retry logic with exponential backoff

- Add configurable max retries
- Add backoff duration calculation
- Add metrics tracking for retries

Fixes #123"
```

### Коммит сообщение шаблон

```
<type>(<scope>): <subject>

<Blank line>
<body> — Подробное описание

<Blank line>
<footer> — Reference to issues, breaking changes, etc.
```

## Добавить себя как contributor

1. **Добавить себя** в `CONTRIBUTORS.md`
2. **Формат:** `- [Name](GitHub profile) - role`

```markdown
# Contributors

- [John Doe](https://github.com/johndoe) - Backend Developer
- [Jane Smith](https://github.com/janesmith) - Frontend Developer
```

## Полезные ссылки

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Python Best Practices](https://peps.python.org/pep-0008/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

## Questions?

- Open an issue на GitHub
- Спросить в discussions
- Email: contributors@example.com

---

**Спасибо за ваш вклад! 🎉**

**Последнее обновление:** 19 октября 2025 г.
