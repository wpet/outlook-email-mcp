"""
Tests for the MCP server module.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


# Import handlers (these are async)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import (
    handle_search_emails,
    handle_get_conversation,
    handle_get_conversations_bulk,
    handle_get_email_body,
    handle_list_attachments,
    call_tool
)


class TestHandleSearchEmails:
    """Tests for search_emails handler."""

    @pytest.mark.asyncio
    async def test_handle_search_emails(self, sample_email):
        """Test search emails handler."""
        mock_results = [
            {
                "id": sample_email["id"],
                "subject": sample_email["subject"],
                "from": "john@example.com"
            }
        ]

        with patch("mcp_server.server.search_emails", return_value=mock_results):
            result = await handle_search_emails({"query": "test", "limit": 10})

        assert result["count"] == 1
        assert len(result["emails"]) == 1

    @pytest.mark.asyncio
    async def test_handle_search_emails_with_filters(self):
        """Test search with multiple filters."""
        with patch("mcp_server.server.search_emails", return_value=[]) as mock_search:
            await handle_search_emails({
                "query": "test",
                "field": "from",
                "from_address": "sender@example.com",
                "since": "2024-01-01",
                "limit": 5
            })

        mock_search.assert_called_once_with(
            query="test",
            field="from",
            from_address="sender@example.com",
            to_address=None,
            subject_contains=None,
            since="2024-01-01",
            until=None,
            limit=5
        )

    @pytest.mark.asyncio
    async def test_handle_search_emails_empty(self):
        """Test search with no results."""
        with patch("mcp_server.server.search_emails", return_value=[]):
            result = await handle_search_emails({})

        assert result["count"] == 0
        assert result["emails"] == []


class TestHandleGetConversation:
    """Tests for get_conversation handler."""

    @pytest.mark.asyncio
    async def test_handle_get_conversation(self, sample_conversation_messages):
        """Test get conversation handler."""
        mock_conversation = {
            "conversation_id": "test_id",
            "subject": "Test Subject",
            "message_count": 2,
            "messages": []
        }

        with patch("mcp_server.server.get_conversation", return_value=mock_conversation):
            result = await handle_get_conversation({"conversation_id": "test_id"})

        assert result["conversation_id"] == "test_id"

    @pytest.mark.asyncio
    async def test_handle_get_conversation_missing_id(self):
        """Test handler with missing conversation_id."""
        result = await handle_get_conversation({})

        assert "error" in result
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_get_conversation_not_found(self):
        """Test handler when conversation not found."""
        with patch("mcp_server.server.get_conversation", return_value=None):
            result = await handle_get_conversation({"conversation_id": "nonexistent"})

        assert "error" in result


class TestHandleGetConversationsBulk:
    """Tests for get_conversations_bulk handler."""

    @pytest.mark.asyncio
    async def test_handle_get_conversations_bulk(self):
        """Test bulk conversations handler."""
        mock_result = {
            "conversations": [{"id": "1"}, {"id": "2"}],
            "stats": {"total": 2, "successful": 2, "failed": 0}
        }

        with patch("mcp_server.server.get_conversations_bulk", return_value=mock_result):
            result = await handle_get_conversations_bulk({
                "conversation_ids": ["id1", "id2"]
            })

        assert result["stats"]["total"] == 2

    @pytest.mark.asyncio
    async def test_handle_get_conversations_bulk_missing_ids(self):
        """Test handler with missing conversation_ids."""
        result = await handle_get_conversations_bulk({})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_get_conversations_bulk_invalid_type(self):
        """Test handler with invalid conversation_ids type."""
        result = await handle_get_conversations_bulk({
            "conversation_ids": "not_a_list"
        })

        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_get_conversations_bulk_exceeds_limit(self):
        """Test handler with too many conversation IDs."""
        result = await handle_get_conversations_bulk({
            "conversation_ids": [f"id{i}" for i in range(25)]
        })

        assert "error" in result
        assert "20" in result["error"]


class TestHandleGetEmailBody:
    """Tests for get_email_body handler."""

    @pytest.mark.asyncio
    async def test_handle_get_email_body(self, sample_email_with_body):
        """Test get email body handler."""
        mock_result = {
            "id": "test_id",
            "subject": "Test",
            "body": "Email content"
        }

        with patch("mcp_server.server.get_email_body", return_value=mock_result):
            result = await handle_get_email_body({
                "email_id": "test_id",
                "format": "text"
            })

        assert result["id"] == "test_id"
        assert result["body"] == "Email content"

    @pytest.mark.asyncio
    async def test_handle_get_email_body_missing_id(self):
        """Test handler with missing email_id."""
        result = await handle_get_email_body({})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_get_email_body_not_found(self):
        """Test handler when email not found."""
        with patch("mcp_server.server.get_email_body", return_value=None):
            result = await handle_get_email_body({"email_id": "nonexistent"})

        assert "error" in result


class TestHandleListAttachments:
    """Tests for list_attachments handler."""

    @pytest.mark.asyncio
    async def test_handle_list_attachments(self, sample_attachments):
        """Test list attachments handler."""
        mock_attachments = [
            {"id": "1", "name": "file.pdf", "size": 1000}
        ]

        with patch("mcp_server.server.get_attachments", return_value=mock_attachments):
            result = await handle_list_attachments({"email_id": "test_id"})

        assert result["email_id"] == "test_id"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_handle_list_attachments_missing_id(self):
        """Test handler with missing email_id."""
        result = await handle_list_attachments({})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_list_attachments_empty(self):
        """Test handler with no attachments."""
        with patch("mcp_server.server.get_attachments", return_value=[]):
            result = await handle_list_attachments({"email_id": "test_id"})

        assert result["count"] == 0
        assert result["attachments"] == []


class TestCallTool:
    """Tests for the main call_tool function."""

    @pytest.mark.asyncio
    async def test_call_tool_auth_failure(self):
        """Test tool call with authentication failure."""
        with patch("mcp_server.server.get_access_token", return_value=None):
            result = await call_tool("search_emails", {"query": "test"})

        # Result should be a list with one TextContent
        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "error" in content
        assert "Authentication" in content["error"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        """Test call with unknown tool name."""
        with patch("mcp_server.server.get_access_token", return_value="token"):
            result = await call_tool("nonexistent_tool", {})

        content = json.loads(result[0].text)
        assert "error" in content

    @pytest.mark.asyncio
    async def test_call_tool_exception_handling(self):
        """Test that exceptions are properly caught and returned."""
        with patch("mcp_server.server.get_access_token", return_value="token"):
            with patch("mcp_server.server.handle_search_emails", side_effect=ValueError("Test error")):
                result = await call_tool("search_emails", {"query": "test"})

        content = json.loads(result[0].text)
        assert "error" in content
        assert "ValueError" in content["error"]

    @pytest.mark.asyncio
    async def test_call_tool_search_emails(self):
        """Test calling search_emails tool."""
        mock_emails = [{"id": "1", "subject": "Test"}]

        with patch("mcp_server.server.get_access_token", return_value="token"):
            with patch("mcp_server.server.search_emails", return_value=mock_emails):
                result = await call_tool("search_emails", {"query": "test"})

        content = json.loads(result[0].text)
        assert content["count"] == 1

    @pytest.mark.asyncio
    async def test_call_tool_get_conversation(self):
        """Test calling get_conversation tool."""
        mock_conv = {"conversation_id": "test", "message_count": 1}

        with patch("mcp_server.server.get_access_token", return_value="token"):
            with patch("mcp_server.server.get_conversation", return_value=mock_conv):
                result = await call_tool("get_conversation", {"conversation_id": "test"})

        content = json.loads(result[0].text)
        assert content["conversation_id"] == "test"
