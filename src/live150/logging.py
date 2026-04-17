import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from live150.config import settings


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
