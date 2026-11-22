import pyroscope


def _init_pyroscope(
    application_name: str,
    host: str,
    port: int,
    secure: bool = False,
) -> None:
    """Инициализирует агент непрерывного профилирования (continuous profiling) Pyroscope.

    Настраивает сбор CPU-профилей с частотой 100 Гц (`oncpu=True`, `gil_only=True`)
    и отправку данных на сервер Pyroscope.

    Args:
        application_name: Имя сервиса, отображаемое в интерфейсе Pyroscope.
        host: Хост сервера Pyroscope.
        port: Порт сервера Pyroscope.
        secure: Использовать ли протокол `https` вместо `http` (по умолчанию `False`).
    """
    scheme = "https" if secure else "http"
    pyroscope.configure(
        application_name=application_name,
        server_address=f"{scheme}://{host}:{port}",
        sample_rate=100,
        oncpu=True,
        gil_only=True,
    )
