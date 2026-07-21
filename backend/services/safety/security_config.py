"""
M4-A8.6 — Neutral module for SSL/TLS configuration.
Manages dev SSL bypass flags securely without hardcoding verify=False.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_LOGGED_SSL_WARNING = False


def is_insecure_ssl_allowed() -> bool:
    """
    Returns True if insecure SSL verification is allowed for local/dev use.
    Always returns False if ENVIRONMENT is set to 'production'.
    """
    dev_only_flag = os.environ.get("ALLOW_INSECURE_SSL_DEV_ONLY", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    env = os.environ.get("ENVIRONMENT", "").strip().lower()

    if dev_only_flag:
        if env == "production":
            return False
        return True
    return False


def get_ssl_verify() -> bool:
    """
    Returns True if SSL/TLS verification should be ON (default),
    or False if ALLOW_INSECURE_SSL_DEV_ONLY is true and we are not in production.
    """
    global _LOGGED_SSL_WARNING
    if is_insecure_ssl_allowed():
        if not _LOGGED_SSL_WARNING:
            logger.warning("TLS verify disabled by dev flag")
            _LOGGED_SSL_WARNING = True
        return False
    return True
