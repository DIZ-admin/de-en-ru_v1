# Инструкции по развертыванию

## Содержание
1. [Окружения](#окружения)
2. [Требования](#требования)
3. [CI/CD Pipeline](#cicd-pipeline)
4. [Deployment процесс](#deployment-процесс)
5. [Мониторинг](#мониторинг)
6. [Rollback](#rollback)

## Окружения

### Staging
- **Backend:** Render/Railway или Docker контейнер
- **Frontend:** Vercel preview branch
- **Database:** Managed PostgreSQL
- **Redis:** Managed Redis
- **Monitoring:** Prometheus + Grafana
- **URL:** `https://staging.de.diz.zone`

### Production
- **Backend:** AWS ECS/Fargate или контейнер на Render/Fly.io
- **Frontend:** Vercel production
- **Database:** AWS RDS PostgreSQL с backup
- **Redis:** AWS ElastiCache
- **Monitoring:** CloudWatch + Grafana + Sentry
- **URL:** `https://de.diz.zone`

## Требования

### Prerequisites
- Docker 24+
- Terraform 1.7+ (для IaC)
- GitHub Actions (CI/CD)
- Доступ к OpenAI API
- Доступ к облачному провайдеру (AWS, Render, Fly.io и т.д.)

### Учетные данные
- Terraform Cloud token
- Docker Registry credentials
- Database credentials
- OpenAI API Key
- Metrics/Monitoring tokens

## CI/CD Pipeline

### GitHub Actions

- **CI (`.github/workflows/ci.yml`)**
  - Триггеры: pull request и push в `main`.
  - Проверки бэкенда: `ruff`, `mypy`, `pytest` через Poetry.
  - Проверки фронтенда: `npm run lint`, `npm test` (Vitest).
  - Docker stage: сборка backend/frontend образов с Buildx (без публикации).
- **Deploy (`.github/workflows/deploy.yml`)**
  - Триггеры: push в `main`, а также ручной `workflow_dispatch`.
  - `deploy-staging`: собирает и пушит образы в GHCR (`:staging` и `:${{ github.sha }}`), шаг-плейсхолдер для IaC.
  - `deploy-production`: требует завершения staging job и одобрения в среде `production`, ретегирует образы как `:latest`.
  - Встроенные permissions позволяют использовать GitHub Container Registry без дополнительных секретов.

> **Примечание:** для реального деплоя интегрируйте шаги Terraform/Helm вместо плейсхолдеров.

## Deployment процесс

### Staging Deployment

1. Создать Pull Request → CI workflow (`ci.yml`) выполнит lint/tests.
2. После мержа в `main` автоматически стартует workflow `Deploy`.
3. Job `deploy-staging` соберёт и опубликует образы в GHCR (`backend`/`frontend`: `staging`, `${SHA}`).
4. В предоставленном плейсхолдере интегрируйте свои Terraform/Helm шаги.
5. Проверить доступность: `curl https://staging.../healthz`, Grafana (порт `3001`), Prometheus (`9090`).

### Production Deployment

1. Убедиться, что `deploy-staging` прошёл успешно и сервис протестирован.
2. Открыть вкладку workflow `Deploy`, дождаться запроса на одобрение среды `production`.
3. После approval job `deploy-production` ретегирует staging-образы как `:latest` и запускает плейсхолдер-деплой (замените на реальный IaC).
4. Провести smoke-тесты и мониторинг (Prometheus/Grafana, OpenAI health).

### Deployment через Docker Compose

**Local/Staging:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

**Production:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Мониторинг

### Компоненты
- **Prometheus** (`monitoring/prometheus.yml`, порт `9090`)
- **Alert rules** (`monitoring/alerting_rules.yml`)
- **Grafana** (`monitoring/grafana/*`, порт `3001`, логин/пароль `admin/admin`)
- **Redis Exporter** (порт `9121`)

### Health Checks

```bash
curl https://de.diz.zone/healthz
```

Пример ответа:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "model": "gpt-4.1-nano",
  "redis": "ok"
}
```

### Alerts

Prometheus правила (`monitoring/alerting_rules.yml`):
- **BackendDown** — `up{job="backend"} == 0` более 1 минуты.
- **HighTranslationLatency** — `histogram_quantile(0.95, translation_latency_seconds_bucket)` > 2s пять минут подряд.
- **ElevatedErrorRate** — доля ошибок > 5% за 5 минут.
- **RateLimitSpike** — `rate_limit_blocked_total` > 5 req/сек (скользящее окно).

### Grafana

- Автопровизия datasource и дашборда `Translator Overview`.
- Основные панели: throughput по статусам, p95 latency, rate-limit blocks.
- Можно добавить оповещения Grafana по тем же метрикам (через Notification channels).

### Logs

**CloudWatch (AWS):**
```bash
aws logs tail /aws/ecs/tritranslator --follow
```

**Application logs:**
```bash
# Backend
docker-compose logs -f backend

# Frontend (Vercel)
# Смотрите в Vercel dashboard
```

## Rollback

### Rollback на предыдущую версию

**Using Terraform:**
```bash
# Получить previous state
terraform state list

# Rollback
terraform apply -var-file=production.tfvars -backup=backup.tfstate

# Или вручную
git revert <commit-hash>
```

**Using Docker:**
```bash
# Получить previous image
docker images | grep backend

# Запустить previous версию
docker-compose up -d --force-recreate backend:previous-tag
```

**Using Git:**
```bash
# Revert к previous commit
git revert HEAD
git push origin main

# CI/CD автоматически передеployит
```

### Процедура Rollback

1. **Detect Issue** — Alert triggered или customer report
2. **Verify Problem** — Проверить logs и metrics
3. **Prepare Rollback** — Identify commit/version для revert
4. **Execute Rollback** — Trigger deployment pipeline
5. **Verify Health** — Run health checks и smoke tests
6. **Notify Team** — Update incident channel
7. **Post-Mortem** — Analyze root cause и prevent future incidents

## Database Migrations

### Schema Changes

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "Add translation_history table"

# Review migration file
cat alembic/versions/*.py

# Apply migration
alembic upgrade head

# Downgrade (если нужно)
alembic downgrade -1
```

### Backup & Restore

```bash
# AWS RDS backup
aws rds create-db-snapshot \
  --db-instance-identifier tritranslator-db \
  --db-snapshot-identifier tritranslator-backup-$(date +%Y%m%d)

# Point-in-time restore
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier tritranslator-db \
  --target-db-instance-identifier tritranslator-db-restored \
  --restore-time 2025-10-19T12:00:00Z
```

## Performance Tuning

### Backend Optimization

```bash
# Adjust worker count
docker-compose up -d --scale backend=3

# Monitor resource usage
docker stats

# Check application metrics
curl https://de.diz.zone/metrics
```

### Redis Optimization

```bash
# Monitor Redis memory
redis-cli info memory

# Cleanup old keys
redis-cli EVAL "return redis.call('del', unpack(redis.call('keys', 'translation-cache:*')))" 0
```

### Frontend Optimization

```bash
# Vercel analytics
# Смотрите в Vercel dashboard

# Lighthouse audit
npm run build
npx lighthouse https://de.diz.zone
```

## Security Considerations

### HTTPS + reverse proxy

- Терминируйте TLS на уровне edge-прокси и проксируйте внутрь только по HTTPS.
- Добавьте HSTS, CSP и другие заголовки также на прокси, чтобы защитить статический контент и редиректы.
- Пример фрагмента `nginx.conf`:
  ```nginx
  server {
    listen 443 ssl http2;
    server_name de.example.com;

    ssl_certificate /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self';" always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;

    location / {
      proxy_pass http://backend:8000;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
  }
  ```

### JWT keys & rotation

- Генерируйте RSA 2048 ключи и храните в Secrets Manager (`JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`).
- Для ротации держите активный ключ в `JWT_PRIVATE_KEY[_PATH]` и добавляйте предыдущие публичные ключи в `JWT_ADDITIONAL_PUBLIC_KEYS*`.
- В CI храните PEM в зашифрованном виде (AWS Secrets Manager, Vault, 1Password) и подставляйте в окружение при деплое.

### Secrets Management

- Используйте `terraform`/`ansible` для провижининга секретов в Vault/SSM.
- Пример загрузки OpenAI key в AWS Secrets Manager:
  ```bash
  aws secretsmanager create-secret \
    --name tritranslator/openai-key \
    --secret-string '{"OPENAI_API_KEY":"sk-..."}'
  ```
- При запуске контейнеров прокидывайте секреты через `docker compose --env-file` или `secrets:`.

## Useful Commands

```bash
# Terraform
terraform init
terraform plan
terraform apply
terraform destroy
terraform state list
terraform state show aws_instance.backend

# Docker
docker-compose ps
docker-compose logs backend
docker-compose exec backend bash
docker-compose restart backend

# GitHub CLI
gh workflow run ci.yml
gh deployment list
gh release create v0.2.0

# AWS CLI
aws ecs describe-services --cluster tritranslator --services backend
aws cloudwatch describe-alarms --alarm-names tritranslator-latency-high
```

## Troubleshooting

### Deployment Fails

```bash
# Check logs
gh workflow view
gh run view <run-id> --log

# Retry deployment
gh workflow run ci.yml

# Check Terraform state
terraform show
terraform state list
```

### Application Errors

```bash
# Check health
curl https://de.diz.zone/healthz

# Check logs
docker-compose logs backend
aws logs tail /aws/ecs/tritranslator --follow

# Check metrics
curl https://de.diz.zone/metrics
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check slow queries
redis-cli slowlog get 10

# Check error rate
curl "https://de.diz.zone/metrics" | grep error_rate
```

---

**Последнее обновление:** 19 октября 2025 г.
