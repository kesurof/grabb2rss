# main.py
import uvicorn
import logging

from config import APP_HOST, APP_PORT
from version import APP_VERSION
from logging_config import setup_logging

setup_logging()

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("Démarrage de Grabb2RSS v%s", APP_VERSION)
    logger.info("Écoute sur %s:%s", APP_HOST, APP_PORT)

    uvicorn.run(
        "api:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        log_level="info"
    )
