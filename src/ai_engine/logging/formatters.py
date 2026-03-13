"""
Formatters — formatage structuré des logs, zero dépendance.

Deux formatters stdlib :
- ``StructuredFormatter`` : format lisible humain pour la console
- ``JSONFormatter`` : format JSON machine-parseable pour fichier / collecteur

Ces formatters enrichissent chaque log avec des champs contextuels
(timestamp ISO, level, logger name, extra fields) sans nécessiter structlog.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

# ── Couleurs ANSI par niveau de log ──────────────────────────────────────────
# Inspiré des conventions Loguru / database_logger.py
_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "\033[94m",  # Bleu ciel
    "INFO": "\033[36m",  # Cyan
    "WARNING": "\033[33m",  # Jaune
    "ERROR": "\033[31m",  # Rouge
    "CRITICAL": "\033[91m",  # Rouge vif
}
_RESET = "\033[0m"
_TIMESTAMP_COLOR = "\033[32m"  # Vert pour le timestamp
_LOGGER_NAME_COLOR = "\033[95m"  # Magenta pour le nom du logger
_KV_KEY_COLOR = "\033[97m"  # Blanc vif pour les clés
_KV_VAL_COLOR = "\033[37m"  # Gris clair pour les valeurs


def _supports_color(stream: Any = None) -> bool:
    """Détecte si le terminal supporte les couleurs ANSI."""
    if stream is None:
        stream = sys.stderr
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False
    # Windows: les couleurs ANSI sont supportées depuis Windows 10 1607+
    # via VirtualTerminalLevel ou les terminaux modernes (Windows Terminal, VS Code)
    if sys.platform == "win32":
        return (
            os.environ.get("TERM_PROGRAM") == "vscode"
            or os.environ.get("WT_SESSION") is not None
            or os.environ.get("ANSICON") is not None
            or True
        )
    return True


class StructuredFormatter(logging.Formatter):
    """Format console lisible avec contexte structuré et couleurs ANSI.

    Produit des lignes comme :
        2026-03-11 20:42:17 | INFO | core.engine | Workflow started
          job_id=abc-123

    Les couleurs sont activées automatiquement quand le terminal les supporte,
    ou peuvent être forcées via le paramètre ``colorize``.

    Args:
        extra_fields: Champs additionnels inclus dans chaque log entry.
        colorize: Force les couleurs on/off. None = auto-détection.
    """

    def __init__(
        self,
        extra_fields: dict[str, Any] | None = None,
        colorize: bool | None = None,
        stream: Any = None,
    ) -> None:
        super().__init__()
        self._extra_fields = extra_fields or {}
        # stream est gardé pour réévaluer isatty() à chaque format()
        # colorize=True/False force la valeur ; None = auto via stream.isatty()
        self._stream = stream
        self._colorize_override = colorize  # None means "auto"

    @property
    def _colorize(self) -> bool:
        """Réévalué à chaque appel : fonctionne en TTY et en pipe."""
        if self._colorize_override is not None:
            return self._colorize_override
        target = self._stream if self._stream is not None else sys.stderr
        return _supports_color(target)

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Nom court : enlever le prefix "pyworkflow_engine."
        name = record.name.removeprefix("pyworkflow_engine.")

        level = record.levelname

        # Couleur selon le niveau
        if self._colorize:
            color = _LEVEL_COLORS.get(record.levelname, "")
            line = (
                f"{_TIMESTAMP_COLOR}{timestamp}{_RESET} | "
                f"{color}{level}{_RESET} | "
                f"{_LOGGER_NAME_COLOR}{name}{_RESET} | {color}{record.getMessage()}{_RESET}"
            )
        else:
            line = f"{timestamp} | {level} | {name} | {record.getMessage()}"

        parts = [line]

        # Ajouter uniquement les extra fields passés au call-site via extra={…}
        # On exclut les champs globaux (extra_fields de LoggingConfig) déjà connus
        # du formatter — inutile de les répéter sur chaque ligne.
        global_keys = frozenset(self._extra_fields)
        call_extras: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_LOG_RECORD_KEYS
                and not key.startswith("_")
                and key not in global_keys
            ):
                call_extras[key] = value

        if call_extras:
            # Concaténer les kv directement sur la ligne du message
            # Couleurs fixes : clés en blanc vif, valeurs en gris clair
            # (indépendant de la couleur du niveau de log)
            if self._colorize:
                kv_str = "  ".join(
                    f"{_KV_KEY_COLOR}{k}{_RESET}={_KV_VAL_COLOR}{v}{_RESET}"
                    for k, v in call_extras.items()
                )
                parts[0] += f"  {kv_str}"
            else:
                kv_str = "  ".join(f"{k}={v}" for k, v in call_extras.items())
                parts[0] += f"  {kv_str}"

        # Exception info
        if record.exc_info and record.exc_info[1] is not None:
            parts.append(self.formatException(record.exc_info))

        return "\n".join(parts)


class JSONFormatter(logging.Formatter):
    """Format JSON structuré pour fichiers et collecteurs de logs.

    Produit des lignes JSON comme :
        {"timestamp": "2026-03-10T14:30:00+00:00", "level": "INFO", ...}

    Chaque ligne est un objet JSON valide (JSON Lines / NDJSON).

    Args:
        extra_fields: Champs additionnels inclus dans chaque log entry.
    """

    def __init__(self, extra_fields: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra fields (config-level)
        log_entry.update(self._extra_fields)

        # Extra fields (record-level, passés via `extra={}`)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_KEYS and not key.startswith("_"):
                log_entry[key] = _safe_serialize(value)

        # Exception info
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Stack info
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def _safe_serialize(value: Any) -> Any:
    """Sérialise une valeur pour JSON de manière sûre."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_serialize(v) for k, v in value.items()}
    return str(value)


# Clés standard d'un LogRecord — on les exclut des extras
_STANDARD_LOG_RECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "message",
        "taskName",
    }
)
