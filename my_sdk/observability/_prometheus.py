from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import make_asgi_app

if TYPE_CHECKING:
    from fastapi import FastAPI


def _init_prometheus(app: FastAPI) -> None:
    """Монтирует ASGI-приложение Prometheus для сбора метрик по эндпоинту `/metrics`.

    Args:
        app: Экземпляр приложения `FastAPI`.
    """
    app.mount(path="/metrics", app=make_asgi_app(), name="metrics")
