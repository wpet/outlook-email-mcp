"""
Parsing module for email content.
Provides HTML to text conversion and email formatting.
"""

import re
import html


# =============================================================================
# HTML PARSING
# =============================================================================

def html_to_text(html_content: str) -> str:
    """
    Convert HTML to plain text.

    Args:
        html_content: HTML string to convert

    Returns:
        Plain text string with whitespace cleaned up
    """
    if not html_content:
        return ""

    text = html_content

    # Remove style tags and content
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove script tags and content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Replace block elements with newlines
    text = re.sub(r'<(br|p|div|tr|li)[^>]*>', '\n', text, flags=re.IGNORECASE)

    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    return text.strip()


# =============================================================================
# EMAIL FORMATTING
# =============================================================================

def format_email_summary(email: dict) -> dict:
    """
    Format raw email data for output.

    Args:
        email: Raw email dict from Graph API

    Returns:
        Formatted email dict with cleaned fields
    """
    return {
        "id": email.get("id"),
        "subject": email.get("subject", ""),
        "from": email.get("from", {}).get("emailAddress", {}).get("address", ""),
        "from_name": email.get("from", {}).get("emailAddress", {}).get("name", ""),
        "to": [
            r.get("emailAddress", {}).get("address", "")
            for r in email.get("toRecipients", [])
        ],
        "date": email.get("receivedDateTime", "")[:10] if email.get("receivedDateTime") else "",
        "datetime": email.get("receivedDateTime", ""),
        "preview": email.get("bodyPreview", "")[:200],
        "has_attachments": email.get("hasAttachments", False),
        "conversation_id": email.get("conversationId", ""),
        "importance": email.get("importance", "normal")
    }


def format_email_body(data: dict, format_type: str = "text") -> dict:
    """
    Format email with full body content.

    Args:
        data: Raw email dict from Graph API
        format_type: "text" or "html"

    Returns:
        Formatted email dict with body content
    """
    body = data.get("body", {})
    body_content = body.get("content", "")

    # Convert HTML to text if requested
    if format_type == "text" and body.get("contentType") == "html":
        body_content = html_to_text(body_content)

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


def format_conversation_message(msg: dict, position: int, include_body: bool = True) -> dict:
    """
    Format a single message in a conversation.

    Args:
        msg: Raw message dict from Graph API
        position: Message position in conversation (1-indexed)
        include_body: Whether to include full body text

    Returns:
        Formatted message dict
    """
    body = ""
    if include_body:
        body = msg.get("body", {}).get("content", "")
        if msg.get("body", {}).get("contentType") == "html":
            body = html_to_text(body)

    return {
        "position": position,
        "id": msg.get("id"),
        "date": msg.get("receivedDateTime", ""),
        "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
        "from_name": msg.get("from", {}).get("emailAddress", {}).get("name", ""),
        "preview": msg.get("bodyPreview", "")[:200],
        "body": body if include_body else None
    }
