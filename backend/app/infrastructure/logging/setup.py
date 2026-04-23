from __future__ import annotations

import logging.config


def configure_logging(log_level: str) -> None:
    normalized_level = log_level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "app.infrastructure.logging.json_formatter.JsonFormatter",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": normalized_level,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": normalized_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": normalized_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": normalized_level,
                    "propagate": False,
                },
            },
        }
    )
