"""
Microsoft Graph API Client
Handles authentication and API calls to Microsoft Graph.
"""

import os
import re
import html
import logging
from pathlib import Path
from typing import Optional

import msal
import requests
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION
# =============================================================================

logger = logging.getLogger(__name__)

# Load .env file
ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
TARGET_USER = os.getenv("AZURE_TARGET_USER")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Token cache with expiry
_token_cache: Optional[str] = None
_token_expiry: float = 0  # Unix timestamp

# Request timeout in seconds
REQUEST_TIMEOUT = 30

# =============================================================================
# CACHING
# =============================================================================

# Cache storage: {key: (value, expiry_timestamp)}
_cache: dict[str, tuple[any, float]] = {}

# Cache TTL settings (in seconds)
CACHE_TTL_EMAIL_BODY = 3600      # 1 hour - email bodies never change
CACHE_TTL_CONVERSATION = 300     # 5 min - new replies possible
CACHE_TTL_ATTACHMENTS = 3600     # 1 hour - attachments don't change
CACHE_TTL_SEARCH = 120           # 2 min - new emails come in


def _cache_get(key: str) -> Optional[any]:
    """Get value from cache if not expired."""
    import time
    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            logger.debug(f"Cache hit: {key[:50]}")
            return value
        else:
            del _cache[key]
    return None


def _cache_set(key: str, value: any, ttl: int) -> None:
    """Store value in cache with TTL."""
    import time
    _cache[key] = (value, time.time() + ttl)
    logger.debug(f"Cache set: {key[:50]} (TTL: {ttl}s)")


def cache_clear() -> dict:
    """Clear all caches and return stats."""
    global _cache
    stats = {
        "entries_cleared": len(_cache),
    }
    _cache = {}
    logger.info(f"Cache cleared: {stats['entries_cleared']} entries")
    return stats


def cache_stats() -> dict:
    """Get cache statistics."""
    import time
    now = time.time()
    valid = sum(1 for _, (_, exp) in _cache.items() if exp > now)
    expired = len(_cache) - valid
    return {
        "total_entries": len(_cache),
        "valid_entries": valid,
        "expired_entries": expired,
    }


# =============================================================================
# PARALLEL REQUESTS
# =============================================================================

# Max concurrent requests (respect rate limits)
MAX_PARALLEL_REQUESTS = 5


def _parallel_fetch(fetch_fn, items: list, max_workers: int = None) -> list:
    """
    Execute fetch function in parallel for multiple items.

    Args:
        fetch_fn: Function to call for each item (takes single item as arg)
        items: List of items to process
        max_workers: Max concurrent threads (default: MAX_PARALLEL_REQUESTS)

    Returns:
        List of results in same order as items
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not items:
        return []

    max_workers = max_workers or MAX_PARALLEL_REQUESTS
    max_workers = min(max_workers, len(items))  # Don't create more workers than items

    results = [None] * len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with their index
        future_to_index = {
            executor.submit(fetch_fn, item): i
            for i, item in enumerate(items)
        }

        # Collect results as they complete
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Parallel fetch error for item {index}: {e}")
                results[index] = None

    return results


# =============================================================================
# AUTHENTICATION
# =============================================================================

def get_access_token() -> Optional[str]:
    """
    Obtain access token via client credentials (app-only).
    Token is cached for reuse with expiry check.
    """
    import time
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


def clear_token_cache():
    """Clear the token cache (for refresh)."""
    global _token_cache, _token_expiry
    _token_cache = None
    _token_expiry = 0


# =============================================================================
# API HELPERS
# =============================================================================

def graph_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """
    Make a GET request to Graph API.

    Args:
        endpoint: API endpoint (without base URL)
        params: Query parameters

    Returns:
        JSON response or None on error
    """
    token = get_access_token()
    if not token:
        return None

    url = f"{GRAPH_ENDPOINT}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout after {REQUEST_TIMEOUT}s: {endpoint}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"API error {response.status_code}: {response.text[:200]}")
        return None


# =============================================================================
# EMAIL FUNCTIONS
# =============================================================================

def search_emails(
    query: str,
    field: str = "all",
    from_address: str = None,
    to_address: str = None,
    subject_contains: str = None,
    since: str = None,
    until: str = None,
    limit: int = 50
) -> list[dict]:
    """
    Search emails with various filters.

    Args:
        query: General search term
        field: Where to search (from, to, cc, subject, body, all)
        from_address: Filter by sender
        to_address: Filter by recipient
        subject_contains: Subject contains
        since: From date (YYYY-MM-DD)
        until: To date (YYYY-MM-DD)
        limit: Maximum results

    Returns:
        List of email objects
    """
    # Build search query
    search_parts = []

    if query:
        search_term = query.lstrip("@")
        if field == "from":
            search_parts.append(f'"from:{search_term}"')
        elif field == "to":
            search_parts.append(f'"to:{search_term}"')
        elif field == "cc":
            search_parts.append(f'"cc:{search_term}"')
        elif field == "subject":
            search_parts.append(f'"subject:{search_term}"')
        elif field == "body":
            search_parts.append(f'"body:{search_term}"')
        else:  # all
            search_parts.append(
                f'"from:{search_term}" OR "to:{search_term}" OR "subject:{search_term}"'
            )

    # Extra filters
    if from_address:
        search_parts.append(f'"from:{from_address}"')
    if to_address:
        search_parts.append(f'"to:{to_address}"')
    if subject_contains:
        search_parts.append(f'"subject:{subject_contains}"')

    search_query = " AND ".join(search_parts) if search_parts else None

    # API request
    endpoint = f"/users/{TARGET_USER}/messages"
    params = {
        "$top": min(limit, 50),
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "bodyPreview,hasAttachments,conversationId,importance",
        "$orderby": "receivedDateTime desc"
    }

    # Only add $search if there is a search term
    if search_query:
        params["$search"] = search_query

    all_emails = []
    fetch_limit = limit * 3  # Overfetch for client-side filtering

    while endpoint and len(all_emails) < fetch_limit:
        data = graph_get(endpoint, params)
        if not data:
            break

        emails = data.get("value", [])
        all_emails.extend(emails)

        # Next page
        next_link = data.get("@odata.nextLink")
        if next_link:
            endpoint = next_link.replace(GRAPH_ENDPOINT, "")
            params = None
        else:
            break

    # Client-side filtering for exact matches
    filtered = []
    for email in all_emails:
        if _email_matches(email, query, field, from_address, to_address, subject_contains, since, until):
            filtered.append(_format_email_summary(email))
            if len(filtered) >= limit:
                break

    return filtered


def _email_matches(
    email: dict,
    query: str,
    field: str,
    from_address: str,
    to_address: str,
    subject_contains: str,
    since: str,
    until: str
) -> bool:
    """Check if email matches all filters."""
    # Query match
    if query:
        query_lower = query.lower()
        from_addr = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
        to_addrs = [r.get("emailAddress", {}).get("address", "").lower()
                    for r in email.get("toRecipients", [])]
        cc_addrs = [r.get("emailAddress", {}).get("address", "").lower()
                    for r in email.get("ccRecipients", [])]
        subject = email.get("subject", "").lower()

        if field == "from" and query_lower not in from_addr:
            return False
        elif field == "to" and not any(query_lower in a for a in to_addrs):
            return False
        elif field == "cc" and not any(query_lower in a for a in cc_addrs):
            return False
        elif field == "subject" and query_lower not in subject:
            return False
        elif field == "all":
            if not (query_lower in from_addr or
                    any(query_lower in a for a in to_addrs) or
                    any(query_lower in a for a in cc_addrs) or
                    query_lower in subject):
                return False

    # Date range
    date = email.get("receivedDateTime", "")[:10]
    if since and date < since:
        return False
    if until and date > until:
        return False

    return True


def _format_email_summary(email: dict) -> dict:
    """Format email for output."""
    return {
        "id": email.get("id"),
        "subject": email.get("subject", ""),
        "from": email.get("from", {}).get("emailAddress", {}).get("address", ""),
        "from_name": email.get("from", {}).get("emailAddress", {}).get("name", ""),
        "to": [r.get("emailAddress", {}).get("address", "")
               for r in email.get("toRecipients", [])],
        "date": email.get("receivedDateTime", "")[:10],
        "datetime": email.get("receivedDateTime", ""),
        "preview": email.get("bodyPreview", "")[:200],
        "has_attachments": email.get("hasAttachments", False),
        "conversation_id": email.get("conversationId", ""),
        "importance": email.get("importance", "normal")
    }


def get_email_body(email_id: str, format: str = "text") -> Optional[dict]:
    """
    Get full email body.

    Args:
        email_id: ID of the email
        format: "text" or "html"

    Returns:
        Email with full body (cached for 1 hour)
    """
    # Check cache first
    cache_key = f"email_body:{email_id}:{format}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"/users/{TARGET_USER}/messages/{email_id}"
    params = {
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "body,hasAttachments,conversationId"
    }

    data = graph_get(endpoint, params)
    if not data:
        return None

    body = data.get("body", {})
    body_content = body.get("content", "")

    # Convert HTML to text if requested
    if format == "text" and body.get("contentType") == "html":
        body_content = _html_to_text(body_content)

    result = {
        "id": data.get("id"),
        "subject": data.get("subject", ""),
        "from": data.get("from", {}).get("emailAddress", {}),
        "to": [r.get("emailAddress", {}) for r in data.get("toRecipients", [])],
        "date": data.get("receivedDateTime", ""),
        "body": body_content,
        "has_attachments": data.get("hasAttachments", False),
        "conversation_id": data.get("conversationId", "")
    }

    # Cache the result
    _cache_set(cache_key, result, CACHE_TTL_EMAIL_BODY)
    return result


def _is_valid_conversation_id(conversation_id: str) -> bool:
    """
    Validate conversation_id format to prevent OData injection.
    Microsoft Graph conversation IDs are base64-encoded strings.
    """
    if not conversation_id or len(conversation_id) > 500:
        return False
    # Only base64 characters allowed (including URL-safe variants)
    return bool(re.match(r'^[A-Za-z0-9+/=_-]+$', conversation_id))


def get_conversation(conversation_id: str, include_body: bool = True) -> Optional[dict]:
    """
    Get all emails in a conversation.

    Args:
        conversation_id: Conversation ID
        include_body: Whether to include full body

    Returns:
        Conversation with all messages (cached for 5 min)
    """
    # Validate conversation_id against OData injection
    if not _is_valid_conversation_id(conversation_id):
        logger.warning(f"Invalid conversation_id format: {conversation_id[:50]}...")
        return None

    # Check cache first
    cache_key = f"conversation:{conversation_id}:{include_body}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"/users/{TARGET_USER}/messages"
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body",
        "$top": 100
    }

    data = graph_get(endpoint, params)
    if not data:
        return None

    messages = data.get("value", [])
    # Sort client-side (Graph API doesn't support $orderby with conversationId filter)
    messages.sort(key=lambda m: m.get("receivedDateTime", ""))
    if not messages:
        return None

    # Collect participants
    participants = set()
    for msg in messages:
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        if from_addr:
            participants.add(from_addr)
        for r in msg.get("toRecipients", []):
            addr = r.get("emailAddress", {}).get("address", "")
            if addr:
                participants.add(addr)

    # Format messages
    formatted_messages = []
    for i, msg in enumerate(messages, 1):
        body = msg.get("body", {}).get("content", "") if include_body else ""
        if include_body and msg.get("body", {}).get("contentType") == "html":
            body = _html_to_text(body)

        formatted_messages.append({
            "position": i,
            "id": msg.get("id"),
            "date": msg.get("receivedDateTime", ""),
            "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
            "from_name": msg.get("from", {}).get("emailAddress", {}).get("name", ""),
            "preview": msg.get("bodyPreview", "")[:200],
            "body": body if include_body else None
        })

    dates = [m.get("receivedDateTime", "")[:10] for m in messages if m.get("receivedDateTime")]

    result = {
        "conversation_id": conversation_id,
        "subject": messages[0].get("subject", "") if messages else "",
        "participants": sorted(list(participants)),
        "message_count": len(messages),
        "date_range": f"{min(dates)} to {max(dates)}" if dates else "",
        "messages": formatted_messages
    }

    # Cache the result
    _cache_set(cache_key, result, CACHE_TTL_CONVERSATION)
    return result


def get_conversations_bulk(
    conversation_ids: list[str],
    include_body: bool = True
) -> dict:
    """
    Get multiple conversations in parallel.

    Args:
        conversation_ids: List of conversation IDs
        include_body: Whether to include full body

    Returns:
        Dict with results and timing info
    """
    import time

    if not conversation_ids:
        return {"conversations": [], "stats": {"total": 0}}

    # Remove duplicates while preserving order
    unique_ids = list(dict.fromkeys(conversation_ids))

    start_time = time.time()

    # Fetch in parallel using closure to pass include_body
    def fetch_one(conv_id):
        return get_conversation(conv_id, include_body)

    results = _parallel_fetch(fetch_one, unique_ids)

    elapsed = time.time() - start_time

    # Build response
    conversations = []
    successful = 0
    failed = 0
    cached = 0

    for conv_id, result in zip(unique_ids, results):
        if result is not None:
            conversations.append(result)
            successful += 1
            # Check if this was a cache hit (very fast = cached)
        else:
            failed += 1
            conversations.append({
                "conversation_id": conv_id,
                "error": "Not found or invalid"
            })

    return {
        "conversations": conversations,
        "stats": {
            "total": len(unique_ids),
            "successful": successful,
            "failed": failed,
            "elapsed_ms": round(elapsed * 1000),
            "avg_ms_per_conversation": round(elapsed * 1000 / len(unique_ids)) if unique_ids else 0
        }
    }


def get_attachments(email_id: str) -> list[dict]:
    """
    List attachments of an email.

    Args:
        email_id: ID of the email

    Returns:
        List of attachments (cached for 1 hour)
    """
    # Check cache first
    cache_key = f"attachments:{email_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"/users/{TARGET_USER}/messages/{email_id}/attachments"
    data = graph_get(endpoint)

    if not data:
        return []

    result = [
        {
            "id": att.get("id"),
            "name": att.get("name", ""),
            "size": att.get("size", 0),
            "content_type": att.get("contentType", ""),
            "type": att.get("@odata.type", "").replace("#microsoft.graph.", "")
        }
        for att in data.get("value", [])
    ]

    # Cache the result
    _cache_set(cache_key, result, CACHE_TTL_ATTACHMENTS)
    return result


def _html_to_text(html_content: str) -> str:
    """Convert HTML to plain text."""
    # Remove style tags
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    # Replace block elements with newlines
    text = re.sub(r'<(br|p|div|tr|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Remove all other tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Cleanup whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


# =============================================================================
# TEST HELPER
# =============================================================================

def test_connection():
    """Test the Graph API connection."""
    token = get_access_token()
    if token:
        print(f"Connection OK - Target: {TARGET_USER}")
        # Test a simple query
        emails = search_emails("", limit=1)
        if emails:
            print(f"Test email: {emails[0].get('subject', 'N/A')}")
        return True
    else:
        print("Connection FAILED")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_connection()
