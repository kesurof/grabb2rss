# logging_config.py
import logging
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def setup_logging() -> None:
    """Configure le logging une seule fois avec un format commun."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    class _RedactQueryParamsFilter(logging.Filter):
        """Masque finement les query params sensibles dans les logs."""
        _sensitive_keys = {
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "apikey",
            "key",
            "secret",
            "session",
            "session_token",
            "authorization",
            "auth",
        }

        def _redact_query(self, text: str) -> str:
            if "?" not in text:
                return text
            try:
                parts = urlsplit(text)
                if not parts.query:
                    return text
                query_items = parse_qsl(parts.query, keep_blank_values=True)
                redacted = []
                for k, v in query_items:
                    if k.lower() in self._sensitive_keys:
                        redacted.append((k, "<redacted>"))
                    else:
                        redacted.append((k, v))
                new_query = urlencode(redacted, doseq=True)
                return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
            except Exception:
                # En cas d'échec, on masque tout le query
                return text.split("?", 1)[0] + "?<redacted>"

        def filter(self, record: logging.LogRecord) -> bool:
            try:
                # Redaction ciblée pour uvicorn.access (path dans args[2])
                if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) >= 3:
                    args = list(record.args)
                    path = args[2]
                    if isinstance(path, str) and "?" in path:
                        args[2] = self._redact_query(path)
                        record.args = tuple(args)

                # Redaction générique pour tous les logs applicatifs
                if isinstance(record.msg, str) and "?" in record.msg:
                    record.msg = self._redact_query(record.msg)
                if isinstance(record.args, tuple):
                    new_args = []
                    for arg in record.args:
                        if isinstance(arg, str) and "?" in arg:
                            new_args.append(self._redact_query(arg))
                        else:
                            new_args.append(arg)
                    record.args = tuple(new_args)
            except Exception:
                # Ne jamais bloquer le log si le filtre échoue
                pass
            return True

    try:
        from config import LOG_LEVEL
        level = str(LOG_LEVEL).upper()
    except Exception:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Appliquer le filtre aux logs d'accès Uvicorn et aux logs applicatifs
    logging.getLogger("uvicorn.access").addFilter(_RedactQueryParamsFilter())
    logging.getLogger().addFilter(_RedactQueryParamsFilter())
