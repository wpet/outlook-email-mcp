"""
Email operations module.
Provides search, read, and conversation functions for emails.
"""

import re
import time
import logging
from typing import Optional

from .config import (
    GRAPH_ENDPOINT,
    CACHE_TTL_EMAIL_BODY,
    CACHE_TTL_CONVERSATION,
    CACHE_TTL_ATTACHMENTS
)
from .cache import cache_get, cache_set
from .api import graph_get, parallel_fetch
from .parsing import format_email_summary, format_email_body, format_conversation_message, html_to_text

logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION
# =============================================================================

def is_valid_conversation_id(conversation_id: str) -> bool:
    """
    Validate conversation_id format to prevent OData injection.
    Microsoft Graph conversation IDs are base64-encoded strings.

    Args:
        conversation_id: Conversation ID to validate

    Returns:
        True if valid format
    """
    if not conversation_id or len(conversation_id) > 500:
        return False
    # Only base64 characters allowed (including URL-safe variants)
    return bool(re.match(r'^[A-Za-z0-9+/=_-]+$', conversation_id))


# =============================================================================
# EMAIL SEARCH
# =============================================================================

def search_emails(
    query: str = "",
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
    endpoint = "/me/messages"
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
            filtered.append(format_email_summary(email))
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
        to_addrs = [
            r.get("emailAddress", {}).get("address", "").lower()
            for r in email.get("toRecipients", [])
        ]
        cc_addrs = [
            r.get("emailAddress", {}).get("address", "").lower()
            for r in email.get("ccRecipients", [])
        ]
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


# =============================================================================
# EMAIL BODY
# =============================================================================

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
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"/me/messages/{email_id}"
    params = {
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "body,hasAttachments,conversationId"
    }

    data = graph_get(endpoint, params)
    if not data:
        return None

    result = format_email_body(data, format)

    # Cache the result
    cache_set(cache_key, result, CACHE_TTL_EMAIL_BODY)
    return result


# =============================================================================
# CONVERSATIONS
# =============================================================================

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
    if not is_valid_conversation_id(conversation_id):
        logger.warning(f"Invalid conversation_id format: {conversation_id[:50]}...")
        return None

    # Check cache first
    cache_key = f"conversation:{conversation_id}:{include_body}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = "/me/messages"
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
    formatted_messages = [
        format_conversation_message(msg, i, include_body)
        for i, msg in enumerate(messages, 1)
    ]

    dates = [
        m.get("receivedDateTime", "")[:10]
        for m in messages if m.get("receivedDateTime")
    ]

    result = {
        "conversation_id": conversation_id,
        "subject": messages[0].get("subject", "") if messages else "",
        "participants": sorted(list(participants)),
        "message_count": len(messages),
        "date_range": f"{min(dates)} to {max(dates)}" if dates else "",
        "messages": formatted_messages
    }

    # Cache the result
    cache_set(cache_key, result, CACHE_TTL_CONVERSATION)
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
    if not conversation_ids:
        return {"conversations": [], "stats": {"total": 0}}

    # Remove duplicates while preserving order
    unique_ids = list(dict.fromkeys(conversation_ids))

    start_time = time.time()

    # Fetch in parallel using closure to pass include_body
    def fetch_one(conv_id):
        return get_conversation(conv_id, include_body)

    results = parallel_fetch(fetch_one, unique_ids)

    elapsed = time.time() - start_time

    # Build response
    conversations = []
    successful = 0
    failed = 0

    for conv_id, result in zip(unique_ids, results):
        if result is not None:
            conversations.append(result)
            successful += 1
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


# =============================================================================
# ATTACHMENTS
# =============================================================================

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
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"/me/messages/{email_id}/attachments"
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
    cache_set(cache_key, result, CACHE_TTL_ATTACHMENTS)
    return result


# =============================================================================
# TEST HELPER
# =============================================================================

def test_connection() -> bool:
    """Test the Graph API connection."""
    from .auth import get_access_token

    token = get_access_token()
    if token:
        print("Connection OK")
        # Test a simple query
        emails = search_emails("", limit=1)
        if emails:
            print(f"Test email: {emails[0].get('subject', 'N/A')}")
        return True
    else:
        print("Connection FAILED")
        return False
