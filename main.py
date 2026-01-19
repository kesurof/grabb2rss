# main.py
import uvicorn
import logging
import sys

from config import APP_HOST, APP_PORT, validate_config

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    # Valider la configuration avant de démarrer
    if not validate_config():
        print("\n❌ L'application ne peut pas démarrer avec une configuration invalide")
        sys.exit(1)
    
    print()  # Ligne vide pour séparer
    
    uvicorn.run(
        "api:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        log_level="info"
    )
