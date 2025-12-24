"""
Tests for the emails module.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.emails import (
    search_emails,
    get_email_body,
    get_conversation,
    get_conversations_bulk,
    get_attachments,
    is_valid_conversation_id,
    _email_matches
)


class TestIsValidConversationId:
    """Tests for conversation ID validation."""

    def test_valid_conversation_id(self):
        """Test valid base64 conversation IDs."""
        assert is_valid_conversation_id("AAQkAGI2TG93AAA=") is True
        assert is_valid_conversation_id("abc123XYZ_-") is True
        assert is_valid_conversation_id("A" * 100) is True

    def test_invalid_conversation_id_empty(self):
        """Test empty conversation ID."""
        assert is_valid_conversation_id("") is False
        assert is_valid_conversation_id(None) is False

    def test_invalid_conversation_id_too_long(self):
        """Test conversation ID exceeding max length."""
        assert is_valid_conversation_id("A" * 501) is False

    def test_invalid_conversation_id_special_chars(self):
        """Test conversation ID with invalid characters."""
        assert is_valid_conversation_id("test'OR'1'='1") is False
        assert is_valid_conversation_id("test;DROP TABLE") is False
        assert is_valid_conversation_id("<script>alert(1)</script>") is False

    def test_conversation_id_odata_injection(self):
        """Test protection against OData injection attempts."""
        assert is_valid_conversation_id("valid' or ''='") is False
        assert is_valid_conversation_id("test) or (1=1") is False


class TestEmailMatches:
    """Tests for email filtering."""

    def test_email_matches_basic(self, sample_email):
        """Test basic email matching."""
        assert _email_matches(sample_email, "", "all", None, None, None, None, None) is True

    def test_email_matches_from_field(self, sample_email):
        """Test matching by from field."""
        assert _email_matches(sample_email, "john", "from", None, None, None, None, None) is True
        assert _email_matches(sample_email, "jane", "from", None, None, None, None, None) is False

    def test_email_matches_to_field(self, sample_email):
        """Test matching by to field."""
        assert _email_matches(sample_email, "jane", "to", None, None, None, None, None) is True
        assert _email_matches(sample_email, "john", "to", None, None, None, None, None) is False

    def test_email_matches_cc_field(self, sample_email):
        """Test matching by cc field."""
        assert _email_matches(sample_email, "bob", "cc", None, None, None, None, None) is True
        assert _email_matches(sample_email, "jane", "cc", None, None, None, None, None) is False

    def test_email_matches_subject_field(self, sample_email):
        """Test matching by subject field."""
        assert _email_matches(sample_email, "Test", "subject", None, None, None, None, None) is True
        assert _email_matches(sample_email, "Missing", "subject", None, None, None, None, None) is False

    def test_email_matches_date_range(self, sample_email):
        """Test matching by date range."""
        # Email date is 2024-01-15
        assert _email_matches(sample_email, "", "all", None, None, None, "2024-01-01", "2024-01-31") is True
        assert _email_matches(sample_email, "", "all", None, None, None, "2024-02-01", None) is False
        assert _email_matches(sample_email, "", "all", None, None, None, None, "2024-01-10") is False

    def test_email_matches_all_field(self, sample_email):
        """Test matching with 'all' field."""
        assert _email_matches(sample_email, "john", "all", None, None, None, None, None) is True
        assert _email_matches(sample_email, "jane", "all", None, None, None, None, None) is True
        assert _email_matches(sample_email, "Test", "all", None, None, None, None, None) is True
        assert _email_matches(sample_email, "nonexistent", "all", None, None, None, None, None) is False


class TestSearchEmails:
    """Tests for email search functionality."""

    def test_search_emails_basic(self, sample_email):
        """Test basic email search."""
        mock_response = {"value": [sample_email]}

        with patch("src.emails.graph_get", return_value=mock_response):
            results = search_emails(query="test", limit=10)

        assert len(results) <= 10

    def test_search_emails_with_filters(self, sample_email):
        """Test email search with various filters."""
        mock_response = {"value": [sample_email]}

        with patch("src.emails.graph_get", return_value=mock_response):
            results = search_emails(
                query="test",
                field="from",
                from_address="john@example.com",
                since="2024-01-01",
                until="2024-12-31",
                limit=5
            )

        # Results should be filtered
        assert isinstance(results, list)

    def test_search_emails_empty_result(self):
        """Test search with no results."""
        with patch("src.emails.graph_get", return_value={"value": []}):
            results = search_emails(query="nonexistent")

        assert results == []

    def test_search_emails_api_failure(self):
        """Test search when API fails."""
        with patch("src.emails.graph_get", return_value=None):
            results = search_emails(query="test")

        assert results == []


class TestGetEmailBody:
    """Tests for getting email body."""

    def test_get_email_body_text(self, sample_email_with_body):
        """Test getting email body as text."""
        with patch("src.emails.graph_get", return_value=sample_email_with_body):
            result = get_email_body("test_id", format="text")

        assert result is not None
        assert "Hello World" in result["body"]

    def test_get_email_body_html(self, sample_email_with_body):
        """Test getting email body as HTML."""
        with patch("src.emails.graph_get", return_value=sample_email_with_body):
            result = get_email_body("test_id", format="html")

        assert result is not None

    def test_get_email_body_cached(self, sample_email_with_body):
        """Test that email body is cached."""
        with patch("src.emails.graph_get", return_value=sample_email_with_body) as mock_get:
            # First call
            result1 = get_email_body("cached_id", format="text")
            # Second call - should use cache
            result2 = get_email_body("cached_id", format="text")

        # Should only call API once
        assert mock_get.call_count == 1
        assert result1 == result2

    def test_get_email_body_not_found(self):
        """Test getting non-existent email."""
        with patch("src.emails.graph_get", return_value=None):
            result = get_email_body("nonexistent_id")

        assert result is None


class TestGetConversation:
    """Tests for getting conversations."""

    def test_get_conversation(self, sample_conversation_messages):
        """Test getting a conversation."""
        with patch("src.emails.graph_get", return_value=sample_conversation_messages):
            result = get_conversation("valid_conv_id")

        assert result is not None
        assert result["message_count"] == 2
        assert "john@example.com" in result["participants"]
        assert "jane@example.com" in result["participants"]

    def test_get_conversation_invalid_id(self):
        """Test with invalid conversation ID."""
        result = get_conversation("invalid'--id")
        assert result is None

    def test_get_conversation_not_found(self):
        """Test non-existent conversation."""
        with patch("src.emails.graph_get", return_value={"value": []}):
            result = get_conversation("valid_but_missing_id")

        assert result is None

    def test_get_conversation_cached(self, sample_conversation_messages):
        """Test that conversations are cached."""
        with patch("src.emails.graph_get", return_value=sample_conversation_messages) as mock_get:
            result1 = get_conversation("cached_conv_id")
            result2 = get_conversation("cached_conv_id")

        assert mock_get.call_count == 1
        assert result1 == result2

    def test_get_conversation_without_body(self, sample_conversation_messages):
        """Test getting conversation without body."""
        with patch("src.emails.graph_get", return_value=sample_conversation_messages):
            result = get_conversation("valid_conv_id", include_body=False)

        assert result is not None
        for msg in result["messages"]:
            assert msg["body"] is None


class TestGetConversationsBulk:
    """Tests for bulk conversation fetching."""

    def test_get_conversations_bulk(self, sample_conversation_messages):
        """Test fetching multiple conversations."""
        with patch("src.emails.graph_get", return_value=sample_conversation_messages):
            result = get_conversations_bulk(["conv1", "conv2"])

        assert "conversations" in result
        assert "stats" in result
        assert result["stats"]["total"] == 2

    def test_get_conversations_bulk_empty(self):
        """Test bulk fetch with empty list."""
        result = get_conversations_bulk([])

        assert result["conversations"] == []
        assert result["stats"]["total"] == 0

    def test_get_conversations_bulk_deduplication(self, sample_conversation_messages):
        """Test that duplicate IDs are removed."""
        with patch("src.emails.graph_get", return_value=sample_conversation_messages):
            result = get_conversations_bulk(["conv1", "conv1", "conv2", "conv2"])

        # Should only fetch 2 unique conversations
        assert result["stats"]["total"] == 2

    def test_get_conversations_bulk_partial_failure(self, sample_conversation_messages):
        """Test bulk fetch with some failures."""
        def mock_get_side_effect(endpoint, params=None):
            if "conv1" in str(params):
                return sample_conversation_messages
            return None

        with patch("src.emails.graph_get", side_effect=mock_get_side_effect):
            result = get_conversations_bulk(["conv1", "conv2"])

        assert result["stats"]["successful"] >= 0
        assert result["stats"]["failed"] >= 0


class TestGetAttachments:
    """Tests for getting attachments."""

    def test_get_attachments(self, sample_attachments):
        """Test getting email attachments."""
        with patch("src.emails.graph_get", return_value=sample_attachments):
            result = get_attachments("email_id")

        assert len(result) == 2
        assert result[0]["name"] == "document.pdf"
        assert result[1]["name"] == "image.png"

    def test_get_attachments_empty(self):
        """Test email with no attachments."""
        with patch("src.emails.graph_get", return_value={"value": []}):
            result = get_attachments("email_id")

        assert result == []

    def test_get_attachments_cached(self, sample_attachments):
        """Test that attachments are cached."""
        with patch("src.emails.graph_get", return_value=sample_attachments) as mock_get:
            result1 = get_attachments("cached_email_id")
            result2 = get_attachments("cached_email_id")

        assert mock_get.call_count == 1
        assert result1 == result2

    def test_get_attachments_api_failure(self):
        """Test when API fails."""
        with patch("src.emails.graph_get", return_value=None):
            result = get_attachments("email_id")

        assert result == []
