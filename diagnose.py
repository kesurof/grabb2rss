#!/usr/bin/env python3
"""
Script de diagnostic complet pour Grabb2RSS
Analyse tous les aspects de l'application et génère un rapport détaillé

Usage:
    python diagnose.py
    # ou dans Docker:
    docker exec grabb2rss python /app/diagnose.py
"""

import json
import os
import sys
import sqlite3
import yaml
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback

class DiagnosticReport:
    def __init__(self):
        self.timestamp = datetime.utcnow().isoformat()
        self.report = {
            "timestamp": self.timestamp,
            "version": "1.0.0",
            "status": "unknown",
            "sections": {}
        }
        self.issues = []
        self.warnings = []

    def add_section(self, name: str, data: Dict[str, Any], status: str = "ok"):
        """Ajoute une section au rapport"""
        self.report["sections"][name] = {
            "status": status,
            "data": data,
            "checked_at": datetime.utcnow().isoformat()
        }

    def add_issue(self, category: str, message: str, severity: str = "error"):
        """Ajoute un problème détecté"""
        self.issues.append({
            "category": category,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        })

    def add_warning(self, category: str, message: str):
        """Ajoute un avertissement"""
        self.warnings.append({
            "category": category,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_overall_status(self) -> str:
        """Détermine le statut global"""
        if any(i["severity"] == "critical" for i in self.issues):
            return "critical"
        elif len(self.issues) > 0:
            return "degraded"
        elif len(self.warnings) > 0:
            return "warning"
        else:
            return "healthy"

    def save_json(self, filename: str = "/config/diagnostic_report.json"):
        """Sauvegarde le rapport en JSON"""
        try:
            self.report["status"] = self.get_overall_status()
            self.report["issues"] = self.issues
            self.report["warnings"] = self.warnings
            self.report["summary"] = {
                "total_issues": len(self.issues),
                "total_warnings": len(self.warnings),
                "critical_issues": len([i for i in self.issues if i["severity"] == "critical"]),
                "errors": len([i for i in self.issues if i["severity"] == "error"])
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Rapport JSON sauvegardé: {filename}")
            return True
        except Exception as e:
            print(f"\n❌ Erreur sauvegarde JSON: {e}")
            return False


def print_header(title: str):
    """Affiche un en-tête de section"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")


def print_subheader(title: str):
    """Affiche un sous-en-tête"""
    print(f"\n{'-' * 80}")
    print(f"  {title}")
    print(f"{'-' * 80}")


def check_filesystem(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie la structure des fichiers et permissions"""
    print_subheader("1. SYSTÈME DE FICHIERS")

    results = {
        "files": {},
        "directories": {},
        "permissions": {}
    }

    # Fichiers critiques à vérifier
    critical_files = [
        "/config/settings.yml",
        "/app/main.py",
        "/app/api.py",
        "/app/config.py",
        "/app/setup.py",
        "/app/db.py"
    ]

    # Répertoires critiques
    critical_dirs = [
        "/config",
        "/app",
        "/app/data",
        "/app/data/torrents",
        "/app/templates",
        "/app/static"
    ]

    print("\n📁 Fichiers critiques:")
    for file_path in critical_files:
        path = Path(file_path)
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        readable = os.access(path, os.R_OK) if exists else False

        status = "✅" if exists and readable else "❌"
        print(f"  {status} {file_path}")
        if exists:
            print(f"      Taille: {size} bytes")
            print(f"      Permissions: {oct(path.stat().st_mode)[-3:]}")
            print(f"      UID/GID: {path.stat().st_uid}/{path.stat().st_gid}")

        results["files"][file_path] = {
            "exists": exists,
            "size": size,
            "readable": readable,
            "permissions": oct(path.stat().st_mode)[-3:] if exists else None
        }

        if not exists:
            report.add_issue("filesystem", f"Fichier manquant: {file_path}", "critical")
        elif not readable:
            report.add_issue("filesystem", f"Fichier non lisible: {file_path}", "error")

    print("\n📂 Répertoires critiques:")
    for dir_path in critical_dirs:
        path = Path(dir_path)
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        writable = os.access(path, os.W_OK) if exists else False

        status = "✅" if exists and is_dir else "❌"
        print(f"  {status} {dir_path}")
        if exists:
            print(f"      Permissions: {oct(path.stat().st_mode)[-3:]}")
            print(f"      Writable: {'Oui' if writable else 'Non'}")

        results["directories"][dir_path] = {
            "exists": exists,
            "is_directory": is_dir,
            "writable": writable,
            "permissions": oct(path.stat().st_mode)[-3:] if exists else None
        }

        if not exists:
            report.add_warning("filesystem", f"Répertoire manquant: {dir_path}")
        elif not writable:
            report.add_warning("filesystem", f"Répertoire non inscriptible: {dir_path}")

    # Informations système
    print("\n💾 Espace disque:")
    try:
        import shutil
        total, used, free = shutil.disk_usage("/config")
        print(f"  Total: {total // (2**30)} GB")
        print(f"  Utilisé: {used // (2**30)} GB")
        print(f"  Libre: {free // (2**30)} GB")
        results["disk_space"] = {
            "total_gb": total // (2**30),
            "used_gb": used // (2**30),
            "free_gb": free // (2**30)
        }
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        results["disk_space"] = {"error": str(e)}

    return results


def check_configuration(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie la configuration settings.yml"""
    print_subheader("2. CONFIGURATION (settings.yml)")

    results = {
        "file_exists": False,
        "valid_yaml": False,
        "content": {},
        "validation": {}
    }

    settings_file = Path("/config/settings.yml")

    if not settings_file.exists():
        print("  ❌ Fichier settings.yml manquant")
        report.add_issue("config", "Fichier settings.yml manquant", "critical")
        return results

    results["file_exists"] = True
    print("  ✅ Fichier settings.yml présent")

    # Lire et parser le YAML
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        results["valid_yaml"] = True
        results["content"] = config
        print("  ✅ YAML valide")
    except Exception as e:
        print(f"  ❌ Erreur parsing YAML: {e}")
        report.add_issue("config", f"YAML invalide: {e}", "critical")
        return results

    # Valider les sections obligatoires
    required_sections = ["prowlarr", "radarr", "sonarr", "sync", "rss"]
    print("\n📋 Sections de configuration:")
    for section in required_sections:
        exists = section in config
        status = "✅" if exists else "❌"
        print(f"  {status} {section}")
        results["validation"][section] = exists

        if not exists:
            report.add_issue("config", f"Section manquante: {section}", "error")

    # Vérifier setup_completed
    setup_completed = config.get("setup_completed", False)
    print(f"\n🔧 Setup complété: {'✅ Oui' if setup_completed else '⚠️  Non (mode wizard)'}")
    results["setup_completed"] = setup_completed

    if not setup_completed:
        report.add_warning("config", "Setup wizard non complété")

    # Analyser Prowlarr
    print("\n🔗 Prowlarr:")
    prowlarr = config.get("prowlarr", {})
    prowlarr_url = prowlarr.get("url", "")
    prowlarr_key = prowlarr.get("api_key", "")

    if prowlarr_url and prowlarr_key:
        print(f"  ✅ URL: {prowlarr_url}")
        print(f"  ✅ API Key: {'*' * 10}{prowlarr_key[-4:] if len(prowlarr_key) > 4 else '****'}")
    else:
        print(f"  ⚠️  URL: {'Non configurée' if not prowlarr_url else prowlarr_url}")
        print(f"  ⚠️  API Key: {'Non configurée' if not prowlarr_key else 'Configurée'}")
        if not setup_completed:
            report.add_warning("config", "Prowlarr non configuré (normal en mode setup)")
        else:
            report.add_issue("config", "Prowlarr configuré comme complété mais URL/API key manquantes", "error")

    # Analyser Radarr
    print("\n🎬 Radarr:")
    radarr = config.get("radarr", {})
    print(f"  Activé: {'✅ Oui' if radarr.get('enabled') else '⚠️  Non'}")
    print(f"  URL: {radarr.get('url', 'Non configurée')}")

    # Analyser Sonarr
    print("\n📺 Sonarr:")
    sonarr = config.get("sonarr", {})
    print(f"  Activé: {'✅ Oui' if sonarr.get('enabled') else '⚠️  Non'}")
    print(f"  URL: {sonarr.get('url', 'Non configurée')}")

    # Analyser Sync
    print("\n🔄 Synchronisation:")
    sync = config.get("sync", {})
    print(f"  Intervalle: {sync.get('interval', 0)} secondes")
    print(f"  Rétention: {sync.get('retention_hours', 0)} heures")
    print(f"  Auto-purge: {'✅ Oui' if sync.get('auto_purge') else '❌ Non'}")

    # Analyser RSS
    print("\n📡 RSS:")
    rss = config.get("rss", {})
    print(f"  Domaine: {rss.get('domain', 'Non configuré')}")
    print(f"  Schéma: {rss.get('scheme', 'Non configuré')}")
    print(f"  Titre: {rss.get('title', 'Non configuré')}")

    return results


def check_database(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie la base de données SQLite"""
    print_subheader("3. BASE DE DONNÉES")

    results = {
        "file_exists": False,
        "readable": False,
        "tables": {},
        "stats": {}
    }

    db_path = Path("/app/data/grabs.db")

    if not db_path.exists():
        print("  ❌ Base de données manquante")
        report.add_warning("database", "Base de données manquante (sera créée au démarrage)")
        return results

    results["file_exists"] = True
    results["file_size_mb"] = db_path.stat().st_size / (1024 * 1024)
    print(f"  ✅ Base de données présente ({results['file_size_mb']:.2f} MB)")

    # Connexion à la DB
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        results["readable"] = True
        print("  ✅ Connexion réussie")

        # Lister les tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\n📊 Tables ({len(tables)}):")
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  - {table}: {count} entrées")
            results["tables"][table] = count

        # Stats détaillées sur la table grabs
        if "grabs" in tables:
            print("\n🎯 Statistiques grabs:")

            # Nombre total
            total = conn.execute("SELECT COUNT(*) FROM grabs").fetchone()[0]
            print(f"  Total: {total}")

            # Par tracker
            trackers = conn.execute("""
                SELECT tracker, COUNT(*) as count
                FROM grabs
                GROUP BY tracker
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()

            print(f"  Top trackers:")
            for tracker in trackers:
                print(f"    - {tracker[0]}: {tracker[1]}")

            # Derniers grabs
            last_grab = conn.execute("""
                SELECT grabbed_at, title
                FROM grabs
                ORDER BY grabbed_at DESC
                LIMIT 1
            """).fetchone()

            if last_grab:
                print(f"  Dernier grab: {last_grab[0]}")
                print(f"    Titre: {last_grab[1][:60]}...")
                results["stats"]["last_grab"] = last_grab[0]

        # Stats sync_logs
        if "sync_logs" in tables:
            print("\n📝 Dernières synchronisations:")
            logs = conn.execute("""
                SELECT sync_at, status, grabs_count, error
                FROM sync_logs
                ORDER BY sync_at DESC
                LIMIT 5
            """).fetchall()

            for log in logs:
                status_icon = "✅" if log[1] == "success" else "❌"
                print(f"  {status_icon} {log[0]}: {log[2]} grabs")
                if log[3]:
                    print(f"      Erreur: {log[3]}")

        conn.close()

    except Exception as e:
        print(f"  ❌ Erreur connexion: {e}")
        report.add_issue("database", f"Erreur accès DB: {e}", "error")
        results["error"] = str(e)

    return results


def check_services(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie la connectivité aux services externes"""
    print_subheader("4. SERVICES EXTERNES")

    results = {
        "prowlarr": {"status": "unknown"},
        "radarr": {"status": "unknown"},
        "sonarr": {"status": "unknown"}
    }

    # Charger la config
    settings_file = Path("/config/settings.yml")
    if not settings_file.exists():
        print("  ⚠️  Pas de configuration, skip tests de connexion")
        return results

    with open(settings_file, 'r') as f:
        config = yaml.safe_load(f)

    # Tester Prowlarr
    print("\n🔗 Prowlarr:")
    prowlarr = config.get("prowlarr", {})
    prowlarr_url = prowlarr.get("url", "")
    prowlarr_key = prowlarr.get("api_key", "")

    if prowlarr_url and prowlarr_key:
        try:
            response = requests.get(
                f"{prowlarr_url}/api/v1/health",
                headers={"X-Api-Key": prowlarr_key},
                timeout=5
            )
            if response.status_code == 200:
                print(f"  ✅ Connecté: {prowlarr_url}")
                results["prowlarr"]["status"] = "connected"
                results["prowlarr"]["response_time_ms"] = response.elapsed.total_seconds() * 1000
            else:
                print(f"  ❌ Erreur HTTP {response.status_code}")
                report.add_issue("services", f"Prowlarr: HTTP {response.status_code}", "error")
                results["prowlarr"]["status"] = "error"
                results["prowlarr"]["http_code"] = response.status_code
        except requests.Timeout:
            print(f"  ❌ Timeout")
            report.add_issue("services", "Prowlarr: Timeout", "error")
            results["prowlarr"]["status"] = "timeout"
        except requests.ConnectionError as e:
            print(f"  ❌ Connexion impossible: {e}")
            report.add_issue("services", f"Prowlarr: Connexion impossible", "error")
            results["prowlarr"]["status"] = "unreachable"
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            results["prowlarr"]["status"] = "error"
            results["prowlarr"]["error"] = str(e)
    else:
        print(f"  ⚠️  Non configuré")
        results["prowlarr"]["status"] = "not_configured"

    # Tester Radarr
    print("\n🎬 Radarr:")
    radarr = config.get("radarr", {})
    if radarr.get("enabled") and radarr.get("url") and radarr.get("api_key"):
        try:
            response = requests.get(
                f"{radarr['url']}/api/v3/system/status",
                headers={"X-Api-Key": radarr["api_key"]},
                timeout=5
            )
            if response.status_code == 200:
                print(f"  ✅ Connecté: {radarr['url']}")
                results["radarr"]["status"] = "connected"
            else:
                print(f"  ❌ Erreur HTTP {response.status_code}")
                results["radarr"]["status"] = "error"
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            results["radarr"]["status"] = "unreachable"
    else:
        print(f"  ⚠️  Désactivé ou non configuré")
        results["radarr"]["status"] = "disabled"

    # Tester Sonarr
    print("\n📺 Sonarr:")
    sonarr = config.get("sonarr", {})
    if sonarr.get("enabled") and sonarr.get("url") and sonarr.get("api_key"):
        try:
            response = requests.get(
                f"{sonarr['url']}/api/v3/system/status",
                headers={"X-Api-Key": sonarr["api_key"]},
                timeout=5
            )
            if response.status_code == 200:
                print(f"  ✅ Connecté: {sonarr['url']}")
                results["sonarr"]["status"] = "connected"
            else:
                print(f"  ❌ Erreur HTTP {response.status_code}")
                results["sonarr"]["status"] = "error"
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            results["sonarr"]["status"] = "unreachable"
    else:
        print(f"  ⚠️  Désactivé ou non configuré")
        results["sonarr"]["status"] = "disabled"

    return results


def check_api_endpoints(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie les endpoints API locaux"""
    print_subheader("5. ENDPOINTS API")

    results = {"endpoints": {}}

    base_url = "http://localhost:8000"

    endpoints_to_test = [
        ("/health", "Healthcheck"),
        ("/debug", "Debug info"),
        ("/api/stats", "Statistiques"),
        ("/api/sync/status", "Statut sync"),
        ("/", "Page principale"),
        ("/setup", "Setup wizard")
    ]

    print(f"\n🌐 Test des endpoints ({base_url}):")
    for endpoint, description in endpoints_to_test:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=3)
            status_icon = "✅" if response.status_code < 400 else "❌"
            print(f"  {status_icon} {endpoint} ({description}): HTTP {response.status_code}")

            results["endpoints"][endpoint] = {
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "reachable": True
            }

            if response.status_code >= 500:
                report.add_issue("api", f"{endpoint} retourne HTTP {response.status_code}", "error")
            elif response.status_code >= 400:
                report.add_warning("api", f"{endpoint} retourne HTTP {response.status_code}")

        except requests.ConnectionError:
            print(f"  ❌ {endpoint}: Connexion impossible")
            results["endpoints"][endpoint] = {
                "reachable": False,
                "error": "connection_refused"
            }
            report.add_issue("api", f"{endpoint} inaccessible", "critical")
        except requests.Timeout:
            print(f"  ⏱️  {endpoint}: Timeout")
            results["endpoints"][endpoint] = {
                "reachable": False,
                "error": "timeout"
            }
            report.add_issue("api", f"{endpoint} timeout", "error")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")
            results["endpoints"][endpoint] = {
                "reachable": False,
                "error": str(e)
            }

    return results


def check_environment(report: DiagnosticReport) -> Dict[str, Any]:
    """Vérifie les variables d'environnement et l'environnement d'exécution"""
    print_subheader("6. ENVIRONNEMENT")

    results = {
        "python_version": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
        "user": {
            "uid": os.getuid(),
            "gid": os.getgid()
        }
    }

    print(f"\n🐍 Python: {sys.version}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"👤 UID/GID: {os.getuid()}/{os.getgid()}")

    # Variables d'environnement intéressantes
    env_vars = ["PUID", "PGID", "TZ", "PYTHONUNBUFFERED", "PATH"]
    print(f"\n🔧 Variables d'environnement:")
    for var in env_vars:
        value = os.getenv(var, "Non définie")
        print(f"  {var}: {value}")
        results[var.lower()] = value

    # Modules Python importants
    print(f"\n📦 Modules Python:")
    required_modules = ["fastapi", "uvicorn", "yaml", "requests", "sqlite3", "apscheduler"]
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} (manquant)")
            report.add_issue("environment", f"Module Python manquant: {module}", "critical")

    return results


def generate_summary(report: DiagnosticReport):
    """Génère un résumé du diagnostic"""
    print_header("RÉSUMÉ DU DIAGNOSTIC")

    status = report.get_overall_status()
    status_icons = {
        "healthy": "✅",
        "warning": "⚠️",
        "degraded": "❌",
        "critical": "🔴"
    }

    print(f"\n{status_icons.get(status, '❓')} Statut global: {status.upper()}")
    print(f"\n📊 Statistiques:")
    print(f"  - Problèmes critiques: {len([i for i in report.issues if i['severity'] == 'critical'])}")
    print(f"  - Erreurs: {len([i for i in report.issues if i['severity'] == 'error'])}")
    print(f"  - Avertissements: {len(report.warnings)}")

    if report.issues:
        print(f"\n🔴 PROBLÈMES DÉTECTÉS:")
        for issue in report.issues:
            severity_icon = "🔴" if issue["severity"] == "critical" else "❌"
            print(f"  {severity_icon} [{issue['category']}] {issue['message']}")

    if report.warnings:
        print(f"\n⚠️  AVERTISSEMENTS:")
        for warning in report.warnings:
            print(f"  ⚠️  [{warning['category']}] {warning['message']}")

    if not report.issues and not report.warnings:
        print("\n✅ Aucun problème détecté !")


def main():
    """Fonction principale"""
    print_header("DIAGNOSTIC COMPLET - GRABB2RSS")
    print(f"\nDate: {datetime.utcnow().isoformat()}")
    print(f"Hôte: {os.uname().nodename if hasattr(os, 'uname') else 'unknown'}")

    report = DiagnosticReport()

    try:
        # 1. Système de fichiers
        fs_results = check_filesystem(report)
        report.add_section("filesystem", fs_results)

        # 2. Configuration
        config_results = check_configuration(report)
        report.add_section("configuration", config_results)

        # 3. Base de données
        db_results = check_database(report)
        report.add_section("database", db_results)

        # 4. Services externes
        services_results = check_services(report)
        report.add_section("services", services_results)

        # 5. Endpoints API
        api_results = check_api_endpoints(report)
        report.add_section("api", api_results)

        # 6. Environnement
        env_results = check_environment(report)
        report.add_section("environment", env_results)

    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        print(traceback.format_exc())
        report.add_issue("system", f"Erreur critique: {e}", "critical")

    # Générer le résumé
    generate_summary(report)

    # Sauvegarder le rapport JSON
    report.save_json("/config/diagnostic_report.json")

    print(f"\n{'=' * 80}")
    print("✅ Diagnostic terminé")
    print(f"{'=' * 80}\n")

    # Code de sortie basé sur le statut
    status = report.get_overall_status()
    if status == "critical":
        sys.exit(2)
    elif status in ["degraded", "warning"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
