# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le fichier .env s'il existe
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Configuration chargée depuis {env_path}")
else:
    print(f"⚠️  Fichier .env non trouvé à {env_path}")

# Chemins
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "grabs.db"
TORRENT_DIR = DATA_DIR / "torrents"

# Créer les répertoires avec permissions appropriées
try:
    DATA_DIR.mkdir(mode=0o755, exist_ok=True)
    DB_PATH.parent.mkdir(mode=0o755, exist_ok=True)
    TORRENT_DIR.mkdir(mode=0o777, exist_ok=True)
except Exception as e:
    print(f"⚠️  Erreur lors de la création des répertoires: {e}")
    print(f"💡 Vérifiez les permissions sur {DATA_DIR.parent}")


# Prowlarr
PROWLARR_URL = os.getenv("PROWLARR_URL", "http://localhost:9696")
PROWLARR_API_KEY = os.getenv("PROWLARR_API_KEY", "")
PROWLARR_HISTORY_PAGE_SIZE = int(os.getenv("PROWLARR_HISTORY_PAGE_SIZE", "100"))

# Radarr (optionnel - pour vérification)
RADARR_URL = os.getenv("RADARR_URL", "")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")

# Sonarr (optionnel - pour vérification)
SONARR_URL = os.getenv("SONARR_URL", "")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")

# Rétention et purge
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "0")) or None
AUTO_PURGE = os.getenv("AUTO_PURGE", "false").lower() == "true"

# Déduplication
DEDUP_HOURS = int(os.getenv("DEDUP_HOURS", "24"))

# Scheduler
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "3600"))

# Web
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Multi-domaine
RSS_DOMAIN = os.getenv("RSS_DOMAIN", "localhost:8000")
RSS_SCHEME = os.getenv("RSS_SCHEME", "http")

# API
RSS_TITLE = "Grab2RSS"
RSS_DESCRIPTION = "Derniers torrents grabbés via Prowlarr"

# Descriptions pour l'UI
DESCRIPTIONS = {
    "PROWLARR_URL": "URL de votre serveur Prowlarr (ex: http://localhost:9696)",
    "PROWLARR_API_KEY": "Clé API Prowlarr (obtenue depuis Prowlarr Settings → API)",
    "PROWLARR_HISTORY_PAGE_SIZE": "Nombre d'enregistrements à récupérer par sync (50-500)",
    "SYNC_INTERVAL": "Intervalle entre chaque sync en secondes (3600 = 1 heure)",
    "RETENTION_HOURS": "Nombre d'heures avant suppression automatique (168 = 7j, 0 = infini)",
    "DEDUP_HOURS": "Fenêtre de déduplication en heures (24 = 24h glissant)",
    "AUTO_PURGE": "Activer la suppression automatique des anciens grabs",
    "RSS_DOMAIN": "Domaine pour les URLs RSS (ex: grab2rss.example.com)",
    "RSS_SCHEME": "Protocole pour les URLs RSS (http ou https)"
}

def validate_config() -> bool:
    """
    Valide la configuration au démarrage.
    Retourne True si tout est OK, False si erreurs critiques.
    """
    errors = []
    warnings = []
    
    # Vérifications critiques
    if not PROWLARR_API_KEY:
        errors.append("❌ PROWLARR_API_KEY manquante (requis)")
    
    if not PROWLARR_URL:
        errors.append("❌ PROWLARR_URL manquante (requis)")
    
    # Vérifications avertissements
    if SYNC_INTERVAL < 60:
        warnings.append("⚠️  SYNC_INTERVAL < 60s (peut surcharger Prowlarr)")
    
    if SYNC_INTERVAL > 86400:
        warnings.append("⚠️  SYNC_INTERVAL > 24h (sync très espacées)")
    
    if DEDUP_HOURS < 1:
        warnings.append("⚠️  DEDUP_HOURS < 1h (risque élevé de doublons)")
    
    if DEDUP_HOURS > 720:
        warnings.append("⚠️  DEDUP_HOURS > 30j (fenêtre très large)")
    
    if PROWLARR_HISTORY_PAGE_SIZE > 500:
        warnings.append("⚠️  PROWLARR_HISTORY_PAGE_SIZE > 500 (peut être lent)")
    
    if AUTO_PURGE and not RETENTION_HOURS:
        warnings.append("⚠️  AUTO_PURGE activé mais RETENTION_HOURS = 0 (aucune purge)")
    
    # Affichage
    if errors:
        print("\n🚨 Erreurs de configuration critiques:")
        for error in errors:
            print(f"  {error}")
        print("\n💡 Corrigez le fichier .env et relancez l'application\n")
        return False
    
    if warnings:
        print("\n⚠️  Avertissements de configuration:")
        for warning in warnings:
            print(f"  {warning}")
        print()
    
    print("✅ Configuration valide")
    return True
