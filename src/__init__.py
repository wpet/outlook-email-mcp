"""
Microsoft Graph Email Client

Public API exports for email operations.
"""

from .config import (
    TARGET_USER,
    GRAPH_ENDPOINT,
    REQUEST_TIMEOUT,
    MAX_PARALLEL_REQUESTS,
    CACHE_TTL_EMAIL_BODY,
    CACHE_TTL_CONVERSATION,
    CACHE_TTL_ATTACHMENTS,
    CACHE_TTL_SEARCH,
)

from .cache import (
    cache_get,
    cache_set,
    cache_clear,
    cache_stats,
    cache_delete,
)

from .auth import (
    get_access_token,
    clear_token_cache,
    is_token_valid,
)

from .api import (
    graph_get,
    graph_post,
    parallel_fetch,
    graph_batch,
    batch_get_messages,
)

from .parsing import (
    html_to_text,
    format_email_summary,
    format_email_body,
    format_conversation_message,
)

from .emails import (
    search_emails,
    get_email_body,
    get_conversation,
    get_conversations_bulk,
    get_attachments,
    is_valid_conversation_id,
    test_connection,
)

__all__ = [
    # Config
    "TARGET_USER",
    "GRAPH_ENDPOINT",
    "REQUEST_TIMEOUT",
    "MAX_PARALLEL_REQUESTS",
    "CACHE_TTL_EMAIL_BODY",
    "CACHE_TTL_CONVERSATION",
    "CACHE_TTL_ATTACHMENTS",
    "CACHE_TTL_SEARCH",
    # Cache
    "cache_get",
    "cache_set",
    "cache_clear",
    "cache_stats",
    "cache_delete",
    # Auth
    "get_access_token",
    "clear_token_cache",
    "is_token_valid",
    # API
    "graph_get",
    "graph_post",
    "parallel_fetch",
    "graph_batch",
    "batch_get_messages",
    # Parsing
    "html_to_text",
    "format_email_summary",
    "format_email_body",
    "format_conversation_message",
    # Emails
    "search_emails",
    "get_email_body",
    "get_conversation",
    "get_conversations_bulk",
    "get_attachments",
    "is_valid_conversation_id",
    "test_connection",
]
