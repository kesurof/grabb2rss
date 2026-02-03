# logging_config.py
import logging
import os


def setup_logging() -> None:
    """Configure le logging une seule fois avec un format commun."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    try:
        from config import LOG_LEVEL
        level = str(LOG_LEVEL).upper()
    except Exception:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
