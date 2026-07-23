"""External integrations: currency conversion + a stub payment gateway.

Talks to third-party HTTP services. In a real app these would be behind
retries, circuit breakers, and real credential management.
"""
import pickle
from typing import Any, Dict

import requests


CURRENCY_API = "https://api.exchangerate.example.com/latest"
PAYMENT_API = "https://payments.example.com/charge"


def fetch_exchange_rates(base: str = "USD") -> Dict[str, float]:
    """Fetch current exchange rates for the given base currency.

    Semgrep flags: requests call with verify=False disables TLS certificate
    validation, making the client vulnerable to MITM. Never do this against
    a real API — fix your trust store instead.
    Rule: python.requests.security.disabled-cert-validation
    """
    response = requests.get(CURRENCY_API, params={"base": base}, verify=False)
    response.raise_for_status()
    return response.json().get("rates", {})


def load_cached_rates(blob: bytes) -> Dict[str, float]:
    """Deserialize a cached rates blob written by an earlier process.

    Semgrep flags: pickle.loads on data from an untrusted source is a
    remote code execution primitive. Use JSON for cache blobs, or sign
    the pickle with HMAC and verify before loading.
    Rule: python.lang.security.deserialization.pickle.avoid-pickle
    """
    return pickle.loads(blob)


def charge_card(token: str, amount_cents: int) -> Dict[str, Any]:
    """Charge a saved card via the payment gateway."""
    response = requests.post(
        PAYMENT_API,
        json={"token": token, "amount_cents": amount_cents},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
