# my_sdk — Асинхронный «all-inclusive» SDK для микросервисов на FastAPI

 https://annushkastark.github.io/my_sdk/


**`my_sdk`** —  библиотека (*microservice chassis*), чтобы превратить  **FastAPI** ... в джанго)))  в полноценный фреймворк «с батарейками в коробке».

Вместо того чтобы копировать инфраструктурную обвязку из сервиса в сервис, можно установить один пакет и сразу получить настроенные коннекторы к базам данных, кэшу, брокерам сообщений, S3, базовые слои репозиториев и сервисов, структурированное логирование с OpenTelemetry, Prometheus-метрики и единую обработку доменных ошибок.

---

## Что входит в коробку

| Категория | Модуль | Возможности |
| :--- | :--- | :--- |
| **Базы данных и кэш** | `my_sdk.databases` | Асинхронные коннекторы к **PostgreSQL** (`SQLAlchemy 2.0` + `asyncpg`), **ClickHouse** (`clickhouse-connect`) и **Redis** (`redis.asyncio`) с поддержкой `env_prefix` через `pydantic-settings`. |
| **FastAPI Depends** | `my_sdk.depends.session` | Готовый тип-алиас `Session = Annotated[AsyncSession, Depends(...)]` для внедрения сессии БД в эндпоинты. |
| **Слои архитектуры** | `my_sdk.repositories`<br>`my_sdk.services` | Обобщённые CRUD-классы `RepositoryBase[ModelT]` и `ServiceBase[RepoT]` на базе PEP 695 дженериков Python 3.12+. |
| **Брокеры и состояние** | `my_sdk.commons.kafka_*`<br>`my_sdk.commons.state` | Идемпотентный `Producer`, `ConsumerBase` с ручным коммитом смещений и менеджер временного состояния `State` на базе распределённых локов Redis. |
| **S3, Почта и HTTP** | `my_sdk.commons.storage`<br>`my_sdk.commons.email_client`<br>`my_sdk.commons.async_client` | Клиент `S3Storage` (`aioboto3`) с UUID-ключами и санитизацией имён, асинхронный `EmailClient` (`fastapi-mail` + `Jinja2`) и базовый `ApiClientBase` (`httpx`). |
| **Observability** | `my_sdk.observability`<br>`my_sdk.middleware` | Цепочечный `ObservabilityBuilder` (**OpenTelemetry OTLP** для FastAPI/SQLAlchemy/HTTPX, **Prometheus**, **Pyroscope**), `RequestAccessMiddleware` (`X-Request-Id`) и `MetricsMiddleware` (RED-метрики). |
| **Логи, ошибки и типы** | `my_sdk.utils` | JSON-логгер с `contextvars` и `trace_id`, декларативные ошибки `DomainError` + генератор OpenAPI-ответов `errs(...)`, типы Pydantic v2 (`ValidPhone`, `LowerEmailStr`, `ContactStr`, `ValidPassword`). |

---

## Установка

```bash
uv add git+https://github.com<your-username>/my_sdk.git
```

---

## Быстрый старт

```python
from fastapi import FastAPI

from my_sdk.commons.kafka_producer import Producer
from my_sdk.commons.storage import S3Storage
from my_sdk.depends.session import Session
from my_sdk.middleware.metrics import MetricsMiddleware
from my_sdk.middleware.request_access import RequestAccessMiddleware
from my_sdk.observability.builder import ObservabilityBuilder
from my_sdk.utils.errors import DomainError, domain_error_exception_handler

app = FastAPI(title="Example Microservice")

# 1. Единый обработчик доменных ошибок
app.add_exception_handler(DomainError, domain_error_exception_handler)

# 2. Сквозной X-Request-Id, access-логи и Prometheus RED-метрики
app.add_middleware(RequestAccessMiddleware, excluded_urls=frozenset({"/health", "/metrics"}))
app.add_middleware(
    MetricsMiddleware,
    service_name="example-service",
    version="1.0.0",
    excluded_urls=frozenset({"/health", "/metrics"}),
)

# 3. OpenTelemetry-трассировка, метрики и профилирование
(
    ObservabilityBuilder(app, service_name="example-service", service_version="1.0.0")
    .with_otlp("alloy:4317")
    .with_logging()
    .with_httpx()
    .with_fastapi(excluded_urls=["/health", "/metrics"])
    .done()
    .with_prometheus()
)

# 4. Использование сессии БД, S3 и Kafka в эндпоинтах
@app.get("/health")
async def health(session: Session) -> dict[str, str]:
    return {"status": "ok"}
```

---

## Конфигурация через переменные окружения (`.env`)

Все инфраструктурные клиенты автоматически читают параметры из переменных окружения или `.env` и поддерживают переопределение префикса (`env_prefix`) для подключения к нескольким базам/хранилищам в одном сервисе:

```env
# PostgreSQL (префикс по умолчанию: POSTGRES_)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=app_db

# ClickHouse (префикс по умолчанию: CLICKHOUSE_)
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=default

# Redis (префикс по умолчанию: REDIS_)
REDIS_URL=redis://localhost:6379/0

# S3 / MinIO (префикс по умолчанию: S3_)
S3_ENDPOINT=https://example.com
S3_ACCESS_KEY=your_access_key
S3_ACCESS_SECRET_KEY=your_secret_key
S3_BUCKET=my-bucket
S3_REGION=us-east-1
S3_USE_SSL=true

# Apache Kafka (префикс по умолчанию: KAFKA_)
KAFKA_BOOTSTRAP_URL=localhost:9092
KAFKA_GROUP_ID=my-service-group

# SMTP / Email (префикс по умолчанию: MAIL_)
MAIL_SERVER=://example.com
MAIL_PORT=587
MAIL_USERNAME=noreply@example.com
MAIL_PASSWORD=secret
MAIL_FROM=noreply@example.com
MAIL_TEMPLATES_DIR=src/templates
```

---

## Документация и разработка

Локальный запуск и сборка документации на базе **MkDocs Material**:

```bash
# Установить зависимости документации (один раз)
make docs-install

# Запустить локальный сервер документации с live-reload (http://127.0.0.1:8001)
make docs-serve

# Проверить строгую сборку документации
make docs-build

# Опубликовать документацию на GitHub Pages
make docs-deploy

# Проверить код линтером Ruff
make ruff
```

---

## Об авторстве


Распространяется под свободной лицензией **[MIT License](LICENSE)**.

это будет дополняться....навреное ..хочу засунуть туда базового консумера и продюссера для редис стримс и кролика и опциональный модуль аутентификации через все (гугл, яндекс, вк, тг, lodto, keykloack) есть готовые классы надо поискать и проверить



