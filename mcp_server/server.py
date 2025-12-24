#!/usr/bin/env python3
"""
Outlook Email MCP Server

MCP server that provides email search and analysis capabilities to Claude Code.
Enables Claude to search emails and analyze conversations.

Usage:
    python mcp_server/server.py

Configure in .mcp.json to use in Claude Code.
"""

import sys
import json
import logging
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from src.graph_client import (
    search_emails,
    get_email_body,
    get_conversation,
    get_attachments,
    get_access_token
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("outlook-mcp")

# =============================================================================
# MCP SERVER
# =============================================================================

server = Server("outlook-email")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return available tools."""
    return [
        Tool(
            name="search_emails",
            description="""Search Outlook emails with various filters.

Use this tool to find emails based on:
- Email address (from/to/cc)
- Subject
- Date range
- Search term in all fields

Returns a list of emails with subject, sender, date and preview.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (email address, domain, or text). E.g.: '@company.com' or 'john@example.com'"
                    },
                    "field": {
                        "type": "string",
                        "enum": ["from", "to", "cc", "subject", "body", "all"],
                        "default": "all",
                        "description": "Which field to search"
                    },
                    "from_address": {
                        "type": "string",
                        "description": "Filter by specific sender (optional)"
                    },
                    "to_address": {
                        "type": "string",
                        "description": "Filter by specific recipient (optional)"
                    },
                    "subject_contains": {
                        "type": "string",
                        "description": "Subject must contain this (optional)"
                    },
                    "since": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        "description": "Emails from this date (YYYY-MM-DD)"
                    },
                    "until": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        "description": "Emails until this date (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum number of results"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_conversation",
            description="""Get a complete email conversation.

Use this tool after finding a relevant email with search_emails.
Provide the conversation_id to get all emails in that thread.

Returns all messages chronologically with full body text.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "Conversation ID (from search_emails result)"
                    },
                    "include_body": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include full body (default: true)"
                    }
                },
                "required": ["conversation_id"]
            }
        ),
        Tool(
            name="get_email_body",
            description="""Get the full content of a specific email.

Use this tool to read the complete text of an email.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Email ID (from search_emails result)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "html"],
                        "default": "text",
                        "description": "Output format"
                    }
                },
                "required": ["email_id"]
            }
        ),
        Tool(
            name="list_attachments",
            description="""List all attachments of an email.

Shows name, size and type of each attachment.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Email ID"
                    }
                },
                "required": ["email_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool."""
    logger.info(f"Tool call: {name} with {arguments}")

    try:
        # Check authentication
        token = get_access_token()
        if not token:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Authentication failed",
                    "message": "Could not authenticate with Microsoft Graph. Check .env configuration."
                }, ensure_ascii=False)
            )]

        # Route to correct handler
        if name == "search_emails":
            result = await handle_search_emails(arguments)
        elif name == "get_conversation":
            result = await handle_get_conversation(arguments)
        elif name == "get_email_body":
            result = await handle_get_email_body(arguments)
        elif name == "list_attachments":
            result = await handle_list_attachments(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(type(e).__name__),
                "message": str(e)
            }, ensure_ascii=False)
        )]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def handle_search_emails(args: dict) -> dict:
    """Handle search_emails tool."""
    emails = search_emails(
        query=args.get("query", ""),
        field=args.get("field", "all"),
        from_address=args.get("from_address"),
        to_address=args.get("to_address"),
        subject_contains=args.get("subject_contains"),
        since=args.get("since"),
        until=args.get("until"),
        limit=args.get("limit", 20)
    )

    return {
        "count": len(emails),
        "emails": emails
    }


async def handle_get_conversation(args: dict) -> dict:
    """Handle get_conversation tool."""
    conversation_id = args.get("conversation_id")
    if not conversation_id:
        return {"error": "conversation_id is required"}

    include_body = args.get("include_body", True)
    conversation = get_conversation(conversation_id, include_body)

    if not conversation:
        return {"error": "Conversation not found", "conversation_id": conversation_id}

    return conversation


async def handle_get_email_body(args: dict) -> dict:
    """Handle get_email_body tool."""
    email_id = args.get("email_id")
    if not email_id:
        return {"error": "email_id is required"}

    format = args.get("format", "text")
    email = get_email_body(email_id, format)

    if not email:
        return {"error": "Email not found", "email_id": email_id}

    return email


async def handle_list_attachments(args: dict) -> dict:
    """Handle list_attachments tool."""
    email_id = args.get("email_id")
    if not email_id:
        return {"error": "email_id is required"}

    attachments = get_attachments(email_id)

    return {
        "email_id": email_id,
        "count": len(attachments),
        "attachments": attachments
    }


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Start the MCP server."""
    logger.info("Starting Outlook Email MCP Server...")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
