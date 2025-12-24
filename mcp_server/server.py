#!/usr/bin/env python3
"""
Outlook Email MCP Server

MCP server die email zoek- en analysefuncties aanbiedt aan Claude Code.
Hiermee kan Claude emails doorzoeken en conversaties analyseren.

Gebruik:
    python mcp_server/server.py

Configureer in .mcp.json om te gebruiken in Claude Code.
"""

import sys
import json
import logging
import asyncio
from pathlib import Path

# Voeg src toe aan path
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
    """Retourneer beschikbare tools."""
    return [
        Tool(
            name="search_emails",
            description="""Zoek Outlook emails met diverse filters.

Gebruik deze tool om emails te vinden op basis van:
- Email adres (from/to/cc)
- Onderwerp
- Datum range
- Zoekterm in alle velden

Retourneert een lijst van emails met subject, afzender, datum en preview.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Zoekterm (email adres, domein, of tekst). Bijv: '@qualitymasters.com' of 'maarten@example.com'"
                    },
                    "field": {
                        "type": "string",
                        "enum": ["from", "to", "cc", "subject", "body", "all"],
                        "default": "all",
                        "description": "In welk veld te zoeken"
                    },
                    "from_address": {
                        "type": "string",
                        "description": "Filter op specifieke afzender (optioneel)"
                    },
                    "to_address": {
                        "type": "string",
                        "description": "Filter op specifieke ontvanger (optioneel)"
                    },
                    "subject_contains": {
                        "type": "string",
                        "description": "Onderwerp moet dit bevatten (optioneel)"
                    },
                    "since": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        "description": "Emails vanaf deze datum (YYYY-MM-DD)"
                    },
                    "until": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        "description": "Emails tot deze datum (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum aantal resultaten"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_conversation",
            description="""Haal een volledige email conversatie op.

Gebruik deze tool nadat je met search_emails een relevante email hebt gevonden.
Geef de conversation_id mee om alle emails in die thread te krijgen.

Retourneert alle berichten chronologisch met volledige body tekst.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "Conversation ID (uit search_emails resultaat)"
                    },
                    "include_body": {
                        "type": "boolean",
                        "default": True,
                        "description": "Volledige body meegeven (default: true)"
                    }
                },
                "required": ["conversation_id"]
            }
        ),
        Tool(
            name="get_email_body",
            description="""Haal de volledige inhoud van een specifieke email op.

Gebruik deze tool om de complete tekst van een email te lezen.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Email ID (uit search_emails resultaat)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "html"],
                        "default": "text",
                        "description": "Output formaat"
                    }
                },
                "required": ["email_id"]
            }
        ),
        Tool(
            name="list_attachments",
            description="""Lijst alle bijlagen van een email.

Toont naam, grootte en type van elke bijlage.""",
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
    """Voer een tool uit."""
    logger.info(f"Tool call: {name} with {arguments}")

    try:
        # Check authentication
        token = get_access_token()
        if not token:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Authentication failed",
                    "message": "Kon niet authenticeren met Microsoft Graph. Check .env configuratie."
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
    """Start de MCP server."""
    logger.info("Starting Outlook Email MCP Server...")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
