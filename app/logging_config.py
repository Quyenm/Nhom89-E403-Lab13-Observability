from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars

from .pii import scrub_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_data_path(env_name: str, default_rel_path: str) -> Path:
    path = Path(os.getenv(env_name, default_rel_path))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


LOG_PATH = _resolve_data_path("LOG_PATH", "data/logs.jsonl")
AUDIT_LOG_PATH = _resolve_data_path("AUDIT_LOG_PATH", "data/audit.jsonl")


class JsonlFileProcessor:
    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        rendered = structlog.processors.JSONRenderer()(logger, method_name, event_dict)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(rendered + "\n")
        return event_dict


class AuditLogProcessor:
    AUDIT_EVENTS = {"request_received", "response_sent", "incident_enabled", "incident_disabled", "request_failed"}

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if event_dict.get("event") in self.AUDIT_EVENTS:
            AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            audit_record = {
                "ts": event_dict.get("ts"),
                "level": event_dict.get("level"),
                "event": event_dict.get("event"),
                "service": event_dict.get("service"),
                "correlation_id": event_dict.get("correlation_id"),
                "user_id_hash": event_dict.get("user_id_hash"),
                "session_id": event_dict.get("session_id"),
                "feature": event_dict.get("feature"),
            }
            rendered = structlog.processors.JSONRenderer()(logger, method_name, audit_record)
            with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(rendered + "\n")
        return event_dict


def scrub_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    payload = event_dict.get("payload")
    if isinstance(payload, dict):
        event_dict["payload"] = {
            k: scrub_text(v) if isinstance(v, str) else v for k, v in payload.items()
        }
    if "event" in event_dict and isinstance(event_dict["event"], str):
        event_dict["event"] = scrub_text(event_dict["event"])
    for field in ("user_id", "session_id"):
        if field in event_dict and isinstance(event_dict[field], str):
            event_dict[field] = scrub_text(event_dict[field])
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            scrub_event,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            AuditLogProcessor(),
            JsonlFileProcessor(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger() -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger()
