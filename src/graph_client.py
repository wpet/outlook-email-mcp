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
# CONFIGURATIE
# =============================================================================

logger = logging.getLogger(__name__)

# Laad .env bestand
ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
TARGET_USER = os.getenv("AZURE_TARGET_USER")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Token cache met expiry
_token_cache: Optional[str] = None
_token_expiry: float = 0  # Unix timestamp

# Request timeout in seconds
REQUEST_TIMEOUT = 30


# =============================================================================
# AUTHENTICATION
# =============================================================================

def get_access_token() -> Optional[str]:
    """
    Verkrijg access token via client credentials (app-only).
    Token wordt gecached voor hergebruik met expiry check.
    """
    import time
    global _token_cache, _token_expiry

    # Check of cached token nog geldig is (met 5 min marge)
    if _token_cache and time.time() < (_token_expiry - 300):
        return _token_cache

    if not all([CLIENT_ID, TENANT_ID, CLIENT_SECRET]):
        logger.error("Azure credentials niet geconfigureerd in .env")
        return None

    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

    result = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" in result:
        _token_cache = result["access_token"]
        # Token expiry opslaan (default 3600 sec als niet meegegeven)
        expires_in = result.get("expires_in", 3600)
        _token_expiry = time.time() + expires_in
        logger.info(f"Access token verkregen (expiry: {expires_in}s)")
        return _token_cache
    else:
        logger.error(f"Auth failed: {result.get('error_description', 'Unknown')}")
        return None


def clear_token_cache():
    """Clear de token cache (voor refresh)."""
    global _token_cache, _token_expiry
    _token_cache = None
    _token_expiry = 0


# =============================================================================
# API HELPERS
# =============================================================================

def graph_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """
    Maak een GET request naar Graph API.

    Args:
        endpoint: API endpoint (zonder base URL)
        params: Query parameters

    Returns:
        JSON response of None bij fout
    """
    token = get_access_token()
    if not token:
        return None

    url = f"{GRAPH_ENDPOINT}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout na {REQUEST_TIMEOUT}s: {endpoint}")
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
# EMAIL FUNCTIES
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
    Zoek emails met diverse filters.

    Args:
        query: Algemene zoekterm
        field: Waar te zoeken (from, to, cc, subject, body, all)
        from_address: Filter op afzender
        to_address: Filter op ontvanger
        subject_contains: Onderwerp bevat
        since: Vanaf datum (YYYY-MM-DD)
        until: Tot datum (YYYY-MM-DD)
        limit: Maximum resultaten

    Returns:
        Lijst van email objects
    """
    # Bouw search query
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

    # Voeg $search alleen toe als er een zoekterm is
    if search_query:
        params["$search"] = search_query

    all_emails = []
    fetch_limit = limit * 3  # Overfetch voor client-side filtering

    while endpoint and len(all_emails) < fetch_limit:
        data = graph_get(endpoint, params)
        if not data:
            break

        emails = data.get("value", [])
        all_emails.extend(emails)

        # Volgende pagina
        next_link = data.get("@odata.nextLink")
        if next_link:
            endpoint = next_link.replace(GRAPH_ENDPOINT, "")
            params = None
        else:
            break

    # Client-side filtering voor exacte matches
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
    """Check of email voldoet aan alle filters."""
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
    """Format email voor output."""
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
    Haal volledige email body op.

    Args:
        email_id: ID van de email
        format: "text" of "html"

    Returns:
        Email met volledige body
    """
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

    return {
        "id": data.get("id"),
        "subject": data.get("subject", ""),
        "from": data.get("from", {}).get("emailAddress", {}),
        "to": [r.get("emailAddress", {}) for r in data.get("toRecipients", [])],
        "date": data.get("receivedDateTime", ""),
        "body": body_content,
        "has_attachments": data.get("hasAttachments", False),
        "conversation_id": data.get("conversationId", "")
    }


def _is_valid_conversation_id(conversation_id: str) -> bool:
    """
    Valideer conversation_id format om OData injection te voorkomen.
    Microsoft Graph conversation IDs zijn base64-encoded strings.
    """
    if not conversation_id or len(conversation_id) > 500:
        return False
    # Alleen base64 karakters toegestaan (inclusief URL-safe varianten)
    return bool(re.match(r'^[A-Za-z0-9+/=_-]+$', conversation_id))


def get_conversation(conversation_id: str, include_body: bool = True) -> Optional[dict]:
    """
    Haal alle emails in een conversatie op.

    Args:
        conversation_id: Conversation ID
        include_body: Of volledige body mee te geven

    Returns:
        Conversatie met alle berichten
    """
    # Valideer conversation_id tegen OData injection
    if not _is_valid_conversation_id(conversation_id):
        logger.warning(f"Ongeldige conversation_id format: {conversation_id[:50]}...")
        return None

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

    # Verzamel participants
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

    return {
        "conversation_id": conversation_id,
        "subject": messages[0].get("subject", "") if messages else "",
        "participants": sorted(list(participants)),
        "message_count": len(messages),
        "date_range": f"{min(dates)} tot {max(dates)}" if dates else "",
        "messages": formatted_messages
    }


def get_attachments(email_id: str) -> list[dict]:
    """
    Lijst attachments van een email.

    Args:
        email_id: ID van de email

    Returns:
        Lijst van attachments
    """
    endpoint = f"/users/{TARGET_USER}/messages/{email_id}/attachments"
    data = graph_get(endpoint)

    if not data:
        return []

    return [
        {
            "id": att.get("id"),
            "name": att.get("name", ""),
            "size": att.get("size", 0),
            "content_type": att.get("contentType", ""),
            "type": att.get("@odata.type", "").replace("#microsoft.graph.", "")
        }
        for att in data.get("value", [])
    ]


def _html_to_text(html_content: str) -> str:
    """Converteer HTML naar plain text."""
    # Verwijder style tags
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
    # Verwijder script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    # Vervang block elements door newlines
    text = re.sub(r'<(br|p|div|tr|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Verwijder alle overige tags
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
    """Test de Graph API verbinding."""
    token = get_access_token()
    if token:
        print(f"Connection OK - Target: {TARGET_USER}")
        # Test een simpele query
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
