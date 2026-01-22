# main.py
import uvicorn
import logging

from config import APP_HOST, APP_PORT

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("🚀 Démarrage de Grabb2RSS v2.9.0")
    print(f"   Écoute sur {APP_HOST}:{APP_PORT}")

    uvicorn.run(
        "api:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        log_level="info"
    )
