"""
Authentication module for Microsoft Graph API.
Handles OAuth 2.0 client credentials flow and token management.
"""

import time
import logging
from typing import Optional

import msal

from .config import CLIENT_ID, TENANT_ID, CLIENT_SECRET, AUTHORITY, SCOPES

logger = logging.getLogger(__name__)

# =============================================================================
# TOKEN CACHE
# =============================================================================

_token_cache: Optional[str] = None
_token_expiry: float = 0  # Unix timestamp


# =============================================================================
# AUTHENTICATION FUNCTIONS
# =============================================================================

def get_access_token() -> Optional[str]:
    """
    Obtain access token via client credentials (app-only).
    Token is cached for reuse with expiry check.

    Returns:
        Access token string or None on failure
    """
    global _token_cache, _token_expiry

    # Check if cached token is still valid (with 5 min margin)
    if _token_cache and time.time() < (_token_expiry - 300):
        return _token_cache

    if not all([CLIENT_ID, TENANT_ID, CLIENT_SECRET]):
        logger.error("Azure credentials not configured in .env")
        return None

    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

    result = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" in result:
        _token_cache = result["access_token"]
        # Store token expiry (default 3600 sec if not provided)
        expires_in = result.get("expires_in", 3600)
        _token_expiry = time.time() + expires_in
        logger.info(f"Access token obtained (expiry: {expires_in}s)")
        return _token_cache
    else:
        logger.error(f"Auth failed: {result.get('error_description', 'Unknown')}")
        return None


def clear_token_cache() -> None:
    """Clear the token cache (for refresh)."""
    global _token_cache, _token_expiry
    _token_cache = None
    _token_expiry = 0


def is_token_valid() -> bool:
    """
    Check if the current cached token is valid.

    Returns:
        True if token exists and is not expired
    """
    return _token_cache is not None and time.time() < (_token_expiry - 300)
