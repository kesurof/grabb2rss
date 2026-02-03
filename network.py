# network.py
"""
Helpers réseau avec retries/backoff pour les appels externes.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import NETWORK_RETRIES, NETWORK_BACKOFF_SECONDS, NETWORK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def request_with_retries(method: str, url: str, **kwargs: Any) -> requests.Response:
    """
    Effectue une requête HTTP avec retries et backoff exponentiel.

    Args:
        method: Méthode HTTP (GET, POST, ...)
        url: URL complète
        kwargs: paramètres passés à requests.request

    Returns:
        Response requests si succès

    Raises:
        requests.RequestException si échec après retries
    """
    retries = int(kwargs.pop("retries", NETWORK_RETRIES))
    backoff_seconds = float(kwargs.pop("backoff_seconds", NETWORK_BACKOFF_SECONDS))
    timeout = float(kwargs.pop("timeout", NETWORK_TIMEOUT_SECONDS))

    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in RETRY_STATUS_CODES:
                raise requests.HTTPError(
                    f"HTTP {response.status_code} (retryable)",
                    response=response
                )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= retries:
                break

            sleep_seconds = backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Requête échouée (%s %s) tentative %s/%s, retry dans %.1fs: %s",
                method,
                url,
                attempt,
                retries,
                sleep_seconds,
                exc
            )
            time.sleep(sleep_seconds)

    raise last_exc if last_exc else requests.RequestException("Erreur réseau inconnue")
