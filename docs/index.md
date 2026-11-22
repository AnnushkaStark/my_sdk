# my_sdk — Асинхронный «all-inclusive» SDK для микросервисов на FastAPI

**`my_sdk`** — платформенная библиотека (*microservice chassis*), которая превращает лёгкий асинхронный **FastAPI** в полноценный фреймворк «с батарейками в коробке».

Вместо того чтобы копировать инфраструктурную обвязку из сервиса в сервис, вы устанавливаете один пакет и сразу получаете настроенные коннекторы к базам данных, кэшу, брокерам сообщений, S3, базовые слои репозиториев и сервисов, структурированное логирование с OpenTelemetry, Prometheus-метрики и единую обработку доменных ошибок.

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

from my_sdk.depends.session import Session
from my_sdk.middleware.metrics import MetricsMiddleware
from my_sdk.middleware.request_access import RequestAccessMiddleware
from my_sdk.observability.builder import ObservabilityBuilder
from my_sdk.utils.errors import DomainError, domain_error_exception_handler

app = FastAPI(title="Example Microservice")

# 1. Единый обработчик доменных ошибок
app.add_exception_handler(DomainError, domain_error_exception_handler)

# 2. Сквозной X-Request-Id, access-логи и Prometheus RED-метрики
app.add_middleware(
    RequestAccessMiddleware,
    excluded_urls=frozenset({"/health", "/metrics"}),
)
app.add_middleware(
    MetricsMiddleware,
    service_name="example-service",
    version="1.0.0",
    excluded_urls=frozenset({"/health", "/metrics"}),
)

# 3. OpenTelemetry-трассировка, метрики и профилирование
(
    ObservabilityBuilder(
        app,
        service_name="example-service",
        service_version="1.0.0",
    )
    .with_otlp("alloy:4317")
    .with_logging()
    .with_httpx()
    .with_fastapi(excluded_urls=["/health", "/metrics"])
    .done()
    .with_prometheus()
)


# 4. Использование готовой зависимости Session в эндпоинтах
@app.get("/health")
async def health(session: Session) -> dict[str, str]:
    return {"status": "ok"}
```

---

## Разделы документации

* **[Базы данных и кэш](api/databases.md)** — коннекторы PostgreSQL, ClickHouse, Redis и зависимость `Session`.
* **[Репозитории и сервисы](api/architecture.md)** — базовые CRUD-классы `RepositoryBase` и `ServiceBase`.
* **[Интеграции и клиенты](api/commons.md)** — S3-хранилище, Kafka Producer/Consumer, распределённый `State`, почта и HTTP-клиент.
* **[Наблюдаемость и Middleware](api/observability.md)** — `ObservabilityBuilder` (OTLP, Prometheus, Pyroscope) и HTTP-middleware.
* **[Утилиты, ошибки и типы](api/utils.md)** — JSON-логгер с `trace_id`, `DomainError` и валидируемые типы Pydantic v2.

---

## Об авторстве и лицензии

Архитектура библиотеки и весь исходный код основаны на реальном опыте разработки микросервисов на FastAPI. Т.

Распространяется под свободной лицензией **MIT License**.
