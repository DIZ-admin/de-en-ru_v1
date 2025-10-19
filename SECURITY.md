# Документация по безопасности

## Содержание
1. [Обзор](#обзор)
2. [Аутентификация и ключи](#аутентификация-и-ключи)
3. [Управление лимитами](#управление-лимитами)
4. [HTTP-защита и заголовки](#http-защита-и-заголовки)
5. [Управление секретами](#управление-секретами)
6. [Security best practices](#security-best-practices)
7. [TODO перед production](#todo-перед-production)

## Обзор

Текущая реализация охватывает следующие аспекты:

- ✅ JWT-аутентификация с поддержкой HS256 и RS256, `kid` и списком дополнительных ключей для ротации.
- ✅ Redis-based rate limiting с fallback на in-memory и метрикой `rate_limit_blocked_total`.
- ✅ Валидация входных данных Pydantic / FastAPI.
- ✅ CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Permissions-Policy и Referrer-Policy добавляются автоматически (в dev HSTS отключён).
- ✅ CORS настраивается whiltelist’ом через `ALLOWED_ORIGINS`.
- ✅ Prometheus-метрики и алёрты (latency, error-rate, rate-limit spikes).

## Аутентификация и ключи

- **Режимы:** для разработки можно оставить `JWT_ALGORITHM=HS256` и `JWT_SECRET_KEY`. Для prod рекомендуется RS256.
- **Переменные:**
  - `JWT_PRIVATE_KEY_PATH` / `JWT_PRIVATE_KEY`
  - `JWT_PUBLIC_KEY_PATH` / `JWT_PUBLIC_KEY`
  - `JWT_ADDITIONAL_PUBLIC_KEYS_PATHS` / `JWT_ADDITIONAL_PUBLIC_KEYS` (разделитель `||`)
  - `JWT_KID` — опциональный идентификатор активного ключа, попадает в заголовок токена.
- **Ротация:** добавьте старый публичный ключ в `JWT_ADDITIONAL_PUBLIC_KEYS*`, затем переключите приватный/публичный ключ на новый. Верификация токенов идёт по всему пулу.
- **Генерация ключей локально:**
  ```bash
  openssl genrsa -out private.pem 2048
  openssl rsa -in private.pem -pubout -out public.pem
  ```
- **TTL:** `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию 30). Для продакшена можно уменьшить до 15 минут и добавить refresh токены поверх Redis.

## Управление лимитами

- Redis-сценарий удаляет устаревшие значения, считает текущие запросы и хранит окно в ZSET.
- Настройки: `RATE_LIMIT_MAX_CALLS`, `RATE_LIMIT_WINDOW_SECONDS`.
- Fallback: при ошибке Redis сервис пишет предупреждение в лог и откатывается к in-memory реализации, чтобы не блокировать трафик.
- Метрика `rate_limit_blocked_total` помогает отслеживать всплески блокировок — добавлены Prometheus-правила.

## HTTP-защита и заголовки

Middleware `SecurityHeadersMiddleware` добавляет следующие заголовки:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy`: настраивается через `SECURITY_CSP` (дефолт: `default-src 'self'; frame-ancestors 'none'; object-src 'none';`).
- `Strict-Transport-Security`: включается при `app_env != development` и `SECURITY_HSTS_ENABLED=true` (по умолчанию max-age=31536000, includeSubDomains).

При использовании внешнего reverse-proxy (Nginx/Traefik) продублируйте HSTS, CSP и policy-заголовки на edge-уровне, а также включите HTTPS-only (301 redirect).

## Управление секретами

- **Не храните** приватные ключи и секреты в git. Используйте Secrets Manager/Parameter Store/Vault/1Password.
- CI/CD должен подставлять PEM в переменные окружения или монтировать файлы по `JWT_PRIVATE_KEY_PATH`/`JWT_PUBLIC_KEY_PATH`.
- В Kubernetes рекомендуется использовать Secrets + projected volumes (опция `subPath`), в Docker Compose — `docker secrets`.
- Для локальной разработки храните тестовые ключи в `.secrets/` (добавлено в `.gitignore`).
- Бэкап ключей: храните в зашифрованном виде (например, SOPS + KMS) и документируйте процедуру ротации/отзыва.

## Security best practices

- Минимизируйте список CORS-источников, не используйте `*` в production.
- Проверяйте логи (`rate_limit_blocked_total`, `translations_total{status="error"}`) и настройте алёрты.
- Включите TLS termination с современными cipher suites, ALPN и OCSP stapling.
- Активируйте audit logging на reverse-proxy, агрегируйте в отдельный поток (ELK, Loki).
- Ограничьте доступ к Prometheus/Grafana, используйте прокси-авторизацию.
- Добавьте SAST/DAST в CI (Semgrep, Trivy).

## TODO перед production

- Refresh токены и отдельный `/auth/refresh` endpoint.
- Secrets Manager интеграция для RS256 ключей и конфигурации (AWS Secrets Manager / Vault).
- Автоматический перезапуск на обновление ключей (watcher + cache_clear).
- Web Application Firewall / Bot protection на edge.
- Финальный penetration test и threat-modeling.
