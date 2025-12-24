"""
Authentication module for Microsoft Graph API.
Uses delegated permissions with interactive login and token caching.
"""

import logging
from typing import Optional

import msal

from .config import CLIENT_ID, TENANT_ID, AUTHORITY, SCOPES, TOKEN_CACHE_FILE

logger = logging.getLogger(__name__)

# =============================================================================
# TOKEN CACHE
# =============================================================================

def _load_cache() -> msal.SerializableTokenCache:
    """Load token cache from disk."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Save token cache to disk."""
    if cache.has_state_changed:
        TOKEN_CACHE_FILE.write_text(cache.serialize())


# =============================================================================
# AUTHENTICATION FUNCTIONS
# =============================================================================

def get_access_token() -> Optional[str]:
    """
    Obtain access token via interactive login or from cache.

    First attempts to get a cached token. If not available or expired,
    triggers an interactive browser login.

    Returns:
        Access token string or None on failure
    """
    if not all([CLIENT_ID, TENANT_ID]):
        logger.error("Azure credentials not configured in .env")
        return None

    cache = _load_cache()

    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    # Try to get token from cache first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(cache)
            logger.info("Access token obtained from cache")
            return result["access_token"]

    # Otherwise, interactive login required
    logger.info("Interactive login required - opening browser...")
    result = app.acquire_token_interactive(scopes=SCOPES)

    _save_cache(cache)

    if "access_token" in result:
        logger.info("Access token obtained via interactive login")
        return result["access_token"]
    else:
        logger.error(f"Auth failed: {result.get('error_description', 'Unknown')}")
        return None


def clear_token_cache() -> None:
    """Clear the token cache (forces new login)."""
    if TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink()
        logger.info("Token cache cleared")


def is_authenticated() -> bool:
    """
    Check if there is a valid cached token.

    Returns:
        True if a valid token exists in cache
    """
    if not TOKEN_CACHE_FILE.exists():
        return False

    cache = _load_cache()
    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    accounts = app.get_accounts()
    if not accounts:
        return False

    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    return result is not None and "access_token" in result
