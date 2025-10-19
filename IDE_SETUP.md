# IDE Setup Guide

Этот документ содержит инструкции по настройке IDE для проекта de-en-ru_v1.

## VSCode Setup

### 1. Установка расширений

Рекомендуемые расширения для VSCode:
- **Python** (ms-python.python) - основное расширение для Python
- **Pylance** (ms-python.vscode-pylance) - продвинутый type checker
- **mypy Type Checker** (ms-python.mypy-type-checker) - интеграция mypy
- **Ruff** (charliermarsh.ruff) - быстрый linter и formatter

Все расширения указаны в `.vscode/extensions.json` и будут предложены при открытии проекта.

### 2. Автоматическая конфигурация

При открытии проекта в VSCode:
1. Откроется диалог с рекомендацией установить расширения
2. Нажми "Install" для установки всех рекомендуемых расширений
3. VSCode автоматически загрузит конфигурацию из `.vscode/settings.json`

### 3. Перезагрузка Language Server

После установки расширений:
1. Открой Command Palette (Cmd+Shift+P)
2. Введи "Python: Restart Language Server"
3. Нажми Enter

Это перезагрузит Pylance и обновит информацию о типах.

### 4. Проверка конфигурации

Убедись, что:
- Python interpreter установлен на `${workspaceFolder}/backend/.venv/bin/python`
- Type checking mode установлен на "basic"
- Pylance использует установленные type stubs

Проверить можно в:
- Command Palette → "Python: Select Interpreter"
- Должен быть выбран интерпретатор из `.venv`

## PyCharm Setup

### 1. Конфигурация Python Interpreter

1. Открой PyCharm
2. Перейди в **PyCharm → Preferences** (macOS) или **File → Settings** (Linux/Windows)
3. Перейди в **Project: de-en-ru_v1 → Python Interpreter**
4. Нажми на иконку шестеренки и выбери "Add..."
5. Выбери "Existing Environment"
6. Укажи путь: `/Users/kostas/Documents/Projects/de-en-ru_v1/backend/.venv/bin/python`
7. Нажми "OK"

### 2. Конфигурация Type Checker

1. Перейди в **Preferences → Languages & Frameworks → Python → Type Checker**
2. Выбери "mypy" в качестве type checker
3. Убедись, что путь к mypy указан правильно (обычно автоматически)
4. Нажми "OK"

### 3. Конфигурация Inspections

1. Перейди в **Preferences → Editor → Inspections**
2. Убедись, что включены проверки типов:
   - "Python → Type checker"
   - "Python → Unresolved reference"
   - "Python → Unused import"

### 4. Перезагрузка IDE

1. Перейди в **File → Invalidate Caches / Restart**
2. Выбери "Invalidate and Restart"
3. PyCharm перезагрузится и переиндексирует проект

## Проверка конфигурации

### Для VSCode

1. Открой файл `backend/app/auth.py`
2. Наведи курсор на импорт `import jwt`
3. Должна появиться информация о типах из `types-PyJWT`
4. Проверь, что нет ошибок "Cannot find implementation or library stub"

### Для PyCharm

1. Открой файл `backend/app/config.py`
2. Наведи курсор на импорт `from pydantic import Field`
3. Должна появиться информация о типах из `pydantic`
4. Проверь, что нет ошибок "Cannot find implementation or library stub"

## Решение проблем

### Ошибка: "Cannot find implementation or library stub for module named 'pydantic'"

**Решение:**
1. Убедись, что виртуальное окружение активировано
2. Перезагрузи Language Server (VSCode) или перезагрузи IDE (PyCharm)
3. Проверь, что type stubs установлены:
   ```bash
   cd backend
   poetry show | grep types
   ```
4. Если type stubs не установлены, установи их:
   ```bash
   poetry add --group dev types-redis types-PyJWT types-cryptography
   ```

### Ошибка: "Python interpreter not found"

**Решение:**
1. Убедись, что Poetry установлен: `poetry --version`
2. Убедись, что виртуальное окружение создано: `poetry env info`
3. Переустанови зависимости: `poetry install`
4. Обнови путь к интерпретатору в IDE

### Ошибка: "Module 'app' has no attribute 'X'"

**Решение:**
1. Убедись, что `PYTHONPATH` включает `backend/` директорию
2. Перезагрузи Language Server / IDE
3. Проверь, что файл `backend/app/__init__.py` существует

## Дополнительные команды

### Запуск type checker

```bash
cd backend
poetry run mypy app
```

### Запуск тестов

```bash
cd backend
poetry run pytest tests/ -v
```

### Запуск FastAPI сервера

```bash
cd backend
poetry run uvicorn app.main:app --reload
```

### Форматирование кода

```bash
cd backend
poetry run black app tests
```

## Полезные ссылки

- [Pylance Documentation](https://github.com/microsoft/pylance-release)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Pyright Documentation](https://github.com/microsoft/pyright)
- [Poetry Documentation](https://python-poetry.org/docs/)

