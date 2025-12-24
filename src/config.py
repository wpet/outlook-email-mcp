"""
Configuration module for Microsoft Graph API client.
Handles environment variables and constants.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# ENVIRONMENT
# =============================================================================

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
TENANT_ID = os.getenv("AZURE_TENANT_ID")

# =============================================================================
# API CONFIGURATION
# =============================================================================

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read", "User.Read"]

# Token cache file for persistent login
TOKEN_CACHE_FILE = Path(__file__).parent.parent / "token_cache.json"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Request timeout in seconds
REQUEST_TIMEOUT = 30

# Max concurrent requests (respect rate limits)
MAX_PARALLEL_REQUESTS = 5

# =============================================================================
# CACHE SETTINGS
# =============================================================================

# Cache TTL settings (in seconds)
CACHE_TTL_EMAIL_BODY = 3600      # 1 hour - email bodies never change
CACHE_TTL_CONVERSATION = 300     # 5 min - new replies possible
CACHE_TTL_ATTACHMENTS = 3600     # 1 hour - attachments don't change
CACHE_TTL_SEARCH = 120           # 2 min - new emails come in
