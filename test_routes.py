#!/usr/bin/env python3
"""
Script de test pour vérifier que toutes les routes fonctionnent correctement
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from api import app

def test_routes():
    """Teste toutes les routes principales"""
    client = TestClient(app)

    print("🧪 Test des routes...")
    print()

    # Routes publiques (devraient toujours fonctionner)
    public_routes = [
        ("/health", "Health check"),
        ("/debug", "Debug info"),
        ("/test", "Test page"),
        ("/minimal", "Minimal test page"),
    ]

    print("📋 Routes publiques:")
    for route, description in public_routes:
        try:
            response = client.get(route, follow_redirects=False)
            status = "✅" if response.status_code == 200 else f"❌ ({response.status_code})"
            print(f"  {status} {route} - {description}")
        except Exception as e:
            print(f"  ❌ {route} - Erreur: {e}")

    print()

    # Routes HTML (peuvent rediriger vers /setup si premier lancement)
    html_routes = [
        ("/", "Dashboard (racine)"),
        ("/dashboard", "Dashboard"),
        ("/login", "Page de login"),
        ("/setup", "Page de setup"),
    ]

    print("📋 Routes HTML:")
    for route, description in html_routes:
        try:
            response = client.get(route, follow_redirects=False)
            if response.status_code == 200:
                status = "✅ OK"
            elif response.status_code == 307:
                location = response.headers.get("location", "?")
                status = f"➡️  REDIRECT → {location}"
            else:
                status = f"❌ ({response.status_code})"
            print(f"  {status} {route} - {description}")
        except Exception as e:
            print(f"  ❌ {route} - Erreur: {e}")

    print()

    # Routes API
    api_routes = [
        ("/api/setup/status", "Setup status"),
        ("/api/auth/status", "Auth status"),
        ("/api/stats", "Stats"),
        ("/api/grabs", "Grabs"),
    ]

    print("📋 Routes API:")
    for route, description in api_routes:
        try:
            response = client.get(route, follow_redirects=False)
            status = "✅" if response.status_code == 200 else f"❌ ({response.status_code})"
            print(f"  {status} {route} - {description}")
        except Exception as e:
            print(f"  ❌ {route} - Erreur: {e}")

    print()
    print("✅ Tests terminés")

if __name__ == "__main__":
    test_routes()
