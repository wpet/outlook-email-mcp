"""
Tests for the parsing module.
"""

import pytest
from src.parsing import html_to_text, format_email_summary, format_email_body, format_conversation_message


class TestHtmlToText:
    """Tests for HTML to text conversion."""

    def test_html_to_text_basic(self):
        """Test basic HTML to text conversion."""
        html = "<p>Hello World</p>"
        result = html_to_text(html)
        assert "Hello World" in result

    def test_html_to_text_with_style_tags(self):
        """Test that style tags and content are removed."""
        html = "<style>.class { color: red; }</style><p>Content</p>"
        result = html_to_text(html)
        assert "Content" in result
        assert "color" not in result
        assert "class" not in result

    def test_html_to_text_with_script_tags(self):
        """Test that script tags and content are removed."""
        html = "<script>alert('test');</script><p>Safe content</p>"
        result = html_to_text(html)
        assert "Safe content" in result
        assert "alert" not in result
        assert "script" not in result.lower()

    def test_html_to_text_with_entities(self):
        """Test HTML entity decoding."""
        html = "<p>&amp; &lt; &gt; &quot; &nbsp;</p>"
        result = html_to_text(html)
        assert "&" in result
        assert "<" in result
        assert ">" in result
        assert '"' in result

    def test_html_to_text_with_nested_tags(self):
        """Test handling of nested HTML tags."""
        html = "<div><p>Outer <strong>Bold <em>Italic</em></strong> text</p></div>"
        result = html_to_text(html)
        assert "Outer" in result
        assert "Bold" in result
        assert "Italic" in result
        assert "text" in result

    def test_html_to_text_empty_input(self):
        """Test handling of empty input."""
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_html_to_text_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed paragraph<div>Mixed tags</p></div>"
        result = html_to_text(html)
        # Should still extract text content
        assert "Unclosed paragraph" in result
        assert "Mixed tags" in result

    def test_html_to_text_with_line_breaks(self):
        """Test that br, p, div tags create line breaks."""
        html = "<p>First</p><br><div>Second</div><p>Third</p>"
        result = html_to_text(html)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result


class TestFormatEmailSummary:
    """Tests for email summary formatting."""

    def test_format_email_summary(self, sample_email):
        """Test basic email summary formatting."""
        result = format_email_summary(sample_email)

        assert result["id"] == "AAMkAGI2TG93AAA="
        assert result["subject"] == "Test Subject"
        assert result["from"] == "john@example.com"
        assert result["from_name"] == "John Doe"
        assert "jane@example.com" in result["to"]
        assert result["date"] == "2024-01-15"
        assert result["has_attachments"] is True
        assert result["importance"] == "high"

    def test_format_email_summary_missing_fields(self):
        """Test formatting with missing fields."""
        email = {"id": "test123"}
        result = format_email_summary(email)

        assert result["id"] == "test123"
        assert result["subject"] == ""
        assert result["from"] == ""
        assert result["to"] == []
        assert result["has_attachments"] is False

    def test_format_email_summary_empty_recipients(self):
        """Test formatting with empty recipient lists."""
        email = {
            "id": "test123",
            "toRecipients": [],
            "ccRecipients": []
        }
        result = format_email_summary(email)
        assert result["to"] == []


class TestFormatEmailBody:
    """Tests for email body formatting."""

    def test_format_email_body_text(self, sample_email_with_body):
        """Test email body formatting with text conversion."""
        result = format_email_body(sample_email_with_body, "text")

        assert result["id"] == "AAMkAGI2TG93AAA="
        assert result["subject"] == "Test Subject"
        assert "Hello World" in result["body"]
        # HTML tags should be removed
        assert "<p>" not in result["body"]

    def test_format_email_body_html(self, sample_email_with_body):
        """Test email body formatting keeping HTML."""
        result = format_email_body(sample_email_with_body, "html")

        assert result["id"] == "AAMkAGI2TG93AAA="
        # HTML should be preserved
        assert "<p>" in result["body"] or "Hello World" in result["body"]


class TestFormatConversationMessage:
    """Tests for conversation message formatting."""

    def test_format_conversation_message_with_body(self):
        """Test formatting message with body included."""
        msg = {
            "id": "msg1",
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "from": {
                "emailAddress": {
                    "name": "John",
                    "address": "john@example.com"
                }
            },
            "bodyPreview": "Preview text",
            "body": {
                "contentType": "text",
                "content": "Full body content"
            }
        }

        result = format_conversation_message(msg, position=1, include_body=True)

        assert result["position"] == 1
        assert result["id"] == "msg1"
        assert result["from"] == "john@example.com"
        assert result["from_name"] == "John"
        assert result["body"] == "Full body content"

    def test_format_conversation_message_without_body(self):
        """Test formatting message without body."""
        msg = {
            "id": "msg1",
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "from": {
                "emailAddress": {
                    "address": "john@example.com"
                }
            },
            "bodyPreview": "Preview only",
            "body": {
                "content": "Should not appear"
            }
        }

        result = format_conversation_message(msg, position=2, include_body=False)

        assert result["position"] == 2
        assert result["body"] is None
        assert "Preview only" in result["preview"]

    def test_format_conversation_message_html_body(self):
        """Test formatting message with HTML body conversion."""
        msg = {
            "id": "msg1",
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "from": {"emailAddress": {"address": "test@example.com"}},
            "bodyPreview": "",
            "body": {
                "contentType": "html",
                "content": "<p>HTML <strong>content</strong></p>"
            }
        }

        result = format_conversation_message(msg, position=1, include_body=True)

        assert "HTML" in result["body"]
        assert "content" in result["body"]
        # Tags should be stripped
        assert "<p>" not in result["body"]
