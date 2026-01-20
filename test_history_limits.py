#!/usr/bin/env python3
"""
Script de test des limites d'historique
Utilise automatiquement la configuration de grabb2rss
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
import sys

# Import de la config du projet
try:
    import config
    print("✅ Configuration chargée depuis config.py\n")
except Exception as e:
    print(f"❌ Erreur chargement config: {e}")
    sys.exit(1)


def format_date(date_str: str) -> str:
    """Formate une date ISO pour affichage"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return date_str


def test_prowlarr_history(page_size: int) -> Dict:
    """Test l'historique Prowlarr avec un pageSize donné"""
    try:
        response = requests.get(
            f"{config.PROWLARR_URL}/api/v1/history",
            headers={"X-Api-Key": config.PROWLARR_API_KEY},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        records = data.get("records", [])

        # Filtrer les grabs réussis (ce que grabb2rss utilise)
        successful_grabs = [
            r for r in records
            if r.get("eventType") == "releaseGrabbed" and r.get("successful") == True
        ]

        return {
            "total": len(records),
            "successful_grabs": len(successful_grabs),
            "oldest": records[-1].get("date") if records else None,
            "newest": records[0].get("date") if records else None,
            "oldest_grab": successful_grabs[-1].get("date") if successful_grabs else None,
            "newest_grab": successful_grabs[0].get("date") if successful_grabs else None,
        }
    except Exception as e:
        return {"error": str(e)}


def test_radarr_history(page_size: int) -> Dict:
    """Test l'historique Radarr"""
    if not config.RADARR_ENABLED or not config.RADARR_API_KEY:
        return {"error": "Radarr non configuré"}

    try:
        response = requests.get(
            f"{config.RADARR_URL}/api/v3/history",
            headers={"X-Api-Key": config.RADARR_API_KEY},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        records = data.get("records", [])

        grabs = [r for r in records if r.get("eventType") == "grabbed"]

        return {
            "total": len(records),
            "grabs": len(grabs),
            "oldest": records[-1].get("date") if records else None,
            "newest": records[0].get("date") if records else None,
            "oldest_grab": grabs[-1].get("date") if grabs else None,
            "newest_grab": grabs[0].get("date") if grabs else None,
        }
    except Exception as e:
        return {"error": str(e)}


def test_sonarr_history(page_size: int) -> Dict:
    """Test l'historique Sonarr"""
    if not config.SONARR_ENABLED or not config.SONARR_API_KEY:
        return {"error": "Sonarr non configuré"}

    try:
        response = requests.get(
            f"{config.SONARR_URL}/api/v3/history",
            headers={"X-Api-Key": config.SONARR_API_KEY},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        records = data.get("records", [])

        grabs = [r for r in records if r.get("eventType") == "grabbed"]

        return {
            "total": len(records),
            "grabs": len(grabs),
            "oldest": records[-1].get("date") if records else None,
            "newest": records[0].get("date") if records else None,
            "oldest_grab": grabs[-1].get("date") if grabs else None,
            "newest_grab": grabs[0].get("date") if grabs else None,
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 80)
    print("🔍 TEST DES LIMITES D'HISTORIQUE - grabb2rss")
    print("=" * 80)
    print()

    # Afficher la config actuelle
    print("📋 CONFIGURATION ACTUELLE")
    print("-" * 80)
    print(f"Prowlarr URL:           {config.PROWLARR_URL}")
    print(f"Prowlarr pageSize:      {config.PROWLARR_HISTORY_PAGE_SIZE}")
    print(f"Radarr activé:          {config.RADARR_ENABLED}")
    print(f"Sonarr activé:          {config.SONARR_ENABLED}")
    print(f"Sync interval:          {config.SYNC_INTERVAL}s ({config.SYNC_INTERVAL // 3600}h)")
    print(f"Rétention:              {config.RETENTION_HOURS}h ({config.RETENTION_HOURS // 24}j)")
    print()

    # Test Prowlarr avec différents pageSizes
    print("=" * 80)
    print("📡 PROWLARR - Test avec différents pageSizes")
    print("=" * 80)
    print()

    page_sizes = [50, 100, 200, 500, 1000]
    prowlarr_results = []

    for size in page_sizes:
        print(f"Testing pageSize={size}...", end=" ")
        result = test_prowlarr_history(size)
        prowlarr_results.append((size, result))

        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ {result['total']} enregistrements, {result['successful_grabs']} grabs réussis")

    print()
    print("📊 RÉSULTATS DÉTAILLÉS PROWLARR")
    print("-" * 80)
    print(f"{'pageSize':<12} {'Total':<8} {'Grabs':<8} {'Plus ancien grab':<25} {'Plus récent':<25}")
    print("-" * 80)

    for size, result in prowlarr_results:
        if "error" not in result:
            oldest = format_date(result['oldest_grab']) if result['oldest_grab'] else "N/A"
            newest = format_date(result['newest_grab']) if result['newest_grab'] else "N/A"
            print(f"{size:<12} {result['total']:<8} {result['successful_grabs']:<8} {oldest:<25} {newest:<25}")

    print()

    # Analyse Prowlarr
    print("🔍 ANALYSE PROWLARR")
    print("-" * 80)

    if len(prowlarr_results) >= 2:
        # Comparer le plus petit et le plus grand pageSize
        smallest = prowlarr_results[0][1]
        largest = prowlarr_results[-1][1]

        if "error" not in smallest and "error" not in largest:
            if smallest['oldest_grab'] == largest['oldest_grab']:
                print("⚠️  La date la plus ancienne est IDENTIQUE quel que soit le pageSize")
                print("    → Limite TEMPORELLE de l'API Prowlarr")
                print(f"    → Historique disponible jusqu'à: {format_date(largest['oldest_grab'])}")
                print()
                print("💡 Actions possibles:")
                print("    1. Vérifier les paramètres de rétention dans Prowlarr (Settings → General)")
                print("    2. Augmenter la rétention si possible")
                print("    3. Accepter cette limitation")
            else:
                print("✅ Augmenter le pageSize permet de remonter PLUS LOIN dans l'historique")
                print(f"    → Avec pageSize={page_sizes[0]}: jusqu'à {format_date(smallest['oldest_grab'])}")
                print(f"    → Avec pageSize={page_sizes[-1]}: jusqu'à {format_date(largest['oldest_grab'])}")
                print()
                print("💡 Actions recommandées:")
                print(f"    1. Augmenter PROWLARR_HISTORY_PAGE_SIZE à {page_sizes[-1]} ou plus")
                print("    2. Modifier /config/settings.yml ou .env")

    print()

    # Test Radarr
    print("=" * 80)
    print("🎬 RADARR")
    print("=" * 80)
    print()

    radarr_result = test_radarr_history(500)
    if "error" in radarr_result:
        print(f"⚠️  {radarr_result['error']}")
    else:
        print(f"Total enregistrements:  {radarr_result['total']}")
        print(f"Grabs:                  {radarr_result['grabs']}")
        if radarr_result['oldest_grab']:
            print(f"Plus ancien grab:       {format_date(radarr_result['oldest_grab'])}")
        if radarr_result['newest_grab']:
            print(f"Plus récent grab:       {format_date(radarr_result['newest_grab'])}")

    print()

    # Test Sonarr
    print("=" * 80)
    print("📺 SONARR")
    print("=" * 80)
    print()

    sonarr_result = test_sonarr_history(500)
    if "error" in sonarr_result:
        print(f"⚠️  {sonarr_result['error']}")
    else:
        print(f"Total enregistrements:  {sonarr_result['total']}")
        print(f"Grabs:                  {sonarr_result['grabs']}")
        if sonarr_result['oldest_grab']:
            print(f"Plus ancien grab:       {format_date(sonarr_result['oldest_grab'])}")
        if sonarr_result['newest_grab']:
            print(f"Plus récent grab:       {format_date(sonarr_result['newest_grab'])}")

    print()

    # Comparaison des périodes
    print("=" * 80)
    print("🔄 COMPARAISON DES PÉRIODES")
    print("=" * 80)
    print()

    # Prendre le plus grand pageSize de Prowlarr
    prowlarr_data = prowlarr_results[-1][1] if prowlarr_results else {}

    if "error" not in prowlarr_data and "error" not in radarr_result and "error" not in sonarr_result:
        print("Comparaison des dates les plus anciennes:")
        print()

        if prowlarr_data.get('oldest_grab'):
            print(f"  Prowlarr: {format_date(prowlarr_data['oldest_grab'])}")

        if radarr_result.get('oldest_grab'):
            print(f"  Radarr:   {format_date(radarr_result['oldest_grab'])}")

        if sonarr_result.get('oldest_grab'):
            print(f"  Sonarr:   {format_date(sonarr_result['oldest_grab'])}")

        print()
        print("💡 Pour que grabb2rss fonctionne correctement:")
        print("   → Les 3 services doivent avoir l'historique sur la MÊME période")
        print("   → Si Prowlarr remonte jusqu'à J-7 mais Radarr seulement J-2,")
        print("     les grabs entre J-7 et J-2 ne pourront pas être validés")

    print()
    print("=" * 80)
    print("✅ TEST TERMINÉ")
    print("=" * 80)
    print()
    print("📝 Pour plus de détails, consultez: TEST_HISTORIQUE.md")
    print()


if __name__ == "__main__":
    main()
