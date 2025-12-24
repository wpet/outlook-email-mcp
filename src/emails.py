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
    limit: int = 50,
    deep_search: bool = False
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
        deep_search: If True, continues pagination until date boundary (for older emails)

    Returns:
        List of email objects

    Strategy:
        - If only date filters: use $filter (server-side, very fast)
        - If search query: use $search with smart pagination (stop at date boundary)
        - deep_search: continue until we pass the 'since' date (finds older emails)
    """
    # Build search query for $search parameter
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

    # Extra filters for $search
    if from_address:
        search_parts.append(f'"from:{from_address}"')
    if to_address:
        search_parts.append(f'"to:{to_address}"')
    if subject_contains:
        search_parts.append(f'"subject:{subject_contains}"')

    search_query = " AND ".join(search_parts) if search_parts else None

    # Build $filter for date range (server-side filtering)
    filter_parts = []
    if since:
        filter_parts.append(f"receivedDateTime ge {since}T00:00:00Z")
    if until:
        filter_parts.append(f"receivedDateTime le {until}T23:59:59Z")
    filter_query = " and ".join(filter_parts) if filter_parts else None

    # API request
    endpoint = "/me/messages"
    params = {
        "$top": 50,  # Max per page
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "bodyPreview,hasAttachments,conversationId,importance",
        "$orderby": "receivedDateTime desc"
    }

    # Strategy: $filter is much faster but can't combine with $search
    # - Dates only (no query): use $filter (server-side, very fast)
    # - Query only: use $search with pagination
    # - Query + dates: use $filter for dates, client-side filter for query
    #   (this is faster than $search which returns by relevance, not date)

    has_text_query = bool(query or from_address or to_address or subject_contains)
    has_date_filter = bool(since or until)

    if has_date_filter:
        # Always use $filter for dates - much more efficient
        params["$filter"] = filter_query
        # Don't use $search - it can't combine with $filter
        # We'll do text matching client-side
    elif search_query:
        # No dates, use $search for text queries
        params["$search"] = search_query

    filtered = []
    pages_fetched = 0

    # Smart limits based on context
    if has_date_filter:
        # Server-side date filtering is fast, allow many pages
        # The date range naturally limits results
        max_pages = 200
    elif deep_search:
        # Deep search without date: allow more pages
        max_pages = 50
    else:
        # Normal search: stop early
        max_pages = 10

    while endpoint and pages_fetched < max_pages:
        data = graph_get(endpoint, params)
        if not data:
            break

        emails = data.get("value", [])
        if not emails:
            break

        pages_fetched += 1
        oldest_date_in_batch = None

        for email in emails:
            email_date = email.get("receivedDateTime", "")[:10]
            oldest_date_in_batch = email_date

            # Check if email matches our criteria
            if _email_matches(email, query, field, from_address, to_address, subject_contains, since, until):
                filtered.append(format_email_summary(email))

                # Early exit if we have enough results
                if len(filtered) >= limit:
                    logger.info(f"Search complete: found {len(filtered)} matches in {pages_fetched} pages")
                    return filtered

        # For $filter queries (date-based), we can use date boundary for early exit
        # because results are ordered by date desc
        if has_date_filter and since and oldest_date_in_batch and oldest_date_in_batch < since:
            logger.info(f"Reached date boundary ({oldest_date_in_batch} < {since}), stopping")
            break

        # For non-date searches without deep_search, stop after finding some results
        if not deep_search and not has_date_filter and len(filtered) > 0 and pages_fetched >= 3:
            break

        # Next page
        next_link = data.get("@odata.nextLink")
        if next_link:
            endpoint = next_link.replace(GRAPH_ENDPOINT, "")
            params = None
        else:
            break

        # Progress logging for longer searches
        if pages_fetched % 20 == 0:
            logger.info(f"Search progress: {pages_fetched} pages, {len(filtered)} matches so far")

    logger.info(f"Search complete: {len(filtered)} matches found in {pages_fetched} pages")
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
        from_addr = (email.get("from", {}).get("emailAddress", {}).get("address") or "").lower()
        to_addrs = [
            (r.get("emailAddress", {}).get("address") or "").lower()
            for r in email.get("toRecipients", [])
        ]
        cc_addrs = [
            (r.get("emailAddress", {}).get("address") or "").lower()
            for r in email.get("ccRecipients", [])
        ]
        subject = (email.get("subject") or "").lower()

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
