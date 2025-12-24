"""
Pytest fixtures and configuration for tests.
"""

import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_email():
    """Sample email data from Graph API."""
    return {
        "id": "AAMkAGI2TG93AAA=",
        "subject": "Test Subject",
        "from": {
            "emailAddress": {
                "name": "John Doe",
                "address": "john@example.com"
            }
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "name": "Jane Smith",
                    "address": "jane@example.com"
                }
            }
        ],
        "ccRecipients": [
            {
                "emailAddress": {
                    "name": "Bob Wilson",
                    "address": "bob@example.com"
                }
            }
        ],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "bodyPreview": "This is a preview of the email content...",
        "hasAttachments": True,
        "conversationId": "AAQkAGI2TG93AAA=",
        "importance": "high"
    }


@pytest.fixture
def sample_email_with_body():
    """Sample email with full body from Graph API."""
    return {
        "id": "AAMkAGI2TG93AAA=",
        "subject": "Test Subject",
        "from": {
            "emailAddress": {
                "name": "John Doe",
                "address": "john@example.com"
            }
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "name": "Jane Smith",
                    "address": "jane@example.com"
                }
            }
        ],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "body": {
            "contentType": "html",
            "content": "<html><body><p>Hello World</p></body></html>"
        },
        "hasAttachments": False,
        "conversationId": "AAQkAGI2TG93AAA="
    }


@pytest.fixture
def sample_conversation_messages():
    """Sample conversation messages from Graph API."""
    return {
        "value": [
            {
                "id": "msg1",
                "subject": "Original Subject",
                "from": {
                    "emailAddress": {
                        "name": "John",
                        "address": "john@example.com"
                    }
                },
                "toRecipients": [
                    {"emailAddress": {"address": "jane@example.com"}}
                ],
                "receivedDateTime": "2024-01-15T10:00:00Z",
                "bodyPreview": "First message",
                "body": {
                    "contentType": "text",
                    "content": "First message body"
                }
            },
            {
                "id": "msg2",
                "subject": "Re: Original Subject",
                "from": {
                    "emailAddress": {
                        "name": "Jane",
                        "address": "jane@example.com"
                    }
                },
                "toRecipients": [
                    {"emailAddress": {"address": "john@example.com"}}
                ],
                "receivedDateTime": "2024-01-15T11:00:00Z",
                "bodyPreview": "Reply message",
                "body": {
                    "contentType": "text",
                    "content": "Reply message body"
                }
            }
        ]
    }


@pytest.fixture
def sample_attachments():
    """Sample attachments from Graph API."""
    return {
        "value": [
            {
                "id": "att1",
                "name": "document.pdf",
                "size": 12345,
                "contentType": "application/pdf",
                "@odata.type": "#microsoft.graph.fileAttachment"
            },
            {
                "id": "att2",
                "name": "image.png",
                "size": 5678,
                "contentType": "image/png",
                "@odata.type": "#microsoft.graph.fileAttachment"
            }
        ]
    }


@pytest.fixture
def sample_html_email_body():
    """Sample HTML email body for parsing tests."""
    return """
    <html>
    <head>
        <style>
            .header { color: blue; }
        </style>
    </head>
    <body>
        <div class="header">
            <p>Hello World!</p>
        </div>
        <br>
        <p>This is a <strong>test</strong> email.</p>
        <script>alert('test');</script>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <p>Special chars: &amp; &lt; &gt; &quot;</p>
    </body>
    </html>
    """


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_access_token():
    """Mock valid access token."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6Ik..."


@pytest.fixture
def mock_msal_app():
    """Mock MSAL ConfidentialClientApplication."""
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "test_token_123",
        "expires_in": 3600,
        "token_type": "Bearer"
    }
    return mock_app


@pytest.fixture
def mock_graph_response():
    """Mock successful Graph API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": []}
    return mock_response


@pytest.fixture
def mock_graph_error_response():
    """Mock failed Graph API response."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    return mock_response


# =============================================================================
# CACHE FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    # Import here to avoid circular imports
    from src.cache import cache_clear
    from src.auth import clear_token_cache

    # Clear before test
    cache_clear()
    clear_token_cache()

    yield

    # Clear after test
    cache_clear()
    clear_token_cache()


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "AZURE_CLIENT_ID": "test-client-id",
        "AZURE_TENANT_ID": "test-tenant-id",
        "AZURE_CLIENT_SECRET": "test-client-secret",
        "AZURE_TARGET_USER": "test@example.com"
    }
    with patch.dict("os.environ", env_vars):
        yield env_vars
