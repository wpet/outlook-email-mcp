# Outlook Email Export - MCP Server

Een MCP (Model Context Protocol) server waarmee Claude Code direct Outlook emails kan doorzoeken en analyseren.

## Features

- **Email zoeken** - Zoek op afzender, ontvanger, onderwerp, datum
- **Conversatie ophalen** - Haal complete email threads op
- **Email body lezen** - Volledige email inhoud
- **Bijlagen bekijken** - Lijst attachments van emails

## Installatie

```bash
# Activeer venv
source venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt

# Configureer credentials
cp .env.example .env
# Edit .env met je Azure credentials
```

## Azure Setup

1. Ga naar [Azure Portal](https://portal.azure.com)
2. Maak een App Registration
3. Voeg API permission toe: `Mail.Read` (Application)
4. Maak een Client Secret
5. Kopieer Client ID, Tenant ID en Secret naar `.env`

## Gebruik in Claude Code

De MCP server is automatisch beschikbaar na configuratie. Vraag Claude:

```
"Zoek alle emails van maarten@example.com over BTW"

"Vat de conversatie samen die ik met X heb gevoerd over Y"

"Welke openstaande acties staan er in mijn emails met Z?"
```

## Beschikbare Tools

| Tool | Beschrijving |
|------|-------------|
| `search_emails` | Zoek emails met filters |
| `get_conversation` | Haal hele email thread op |
| `get_email_body` | Lees volledige email |
| `list_attachments` | Bekijk bijlagen |

## Testen

```bash
# Test Graph API verbinding
python -c "from src.graph_client import test_connection; test_connection()"

# Test MCP server (in Claude Code)
/mcp
```

## Bestanden

```
├── src/
│   └── graph_client.py    # Microsoft Graph API client
├── mcp_server/
│   └── server.py          # MCP server
├── .mcp.json              # Claude Code configuratie
└── requirements.txt       # Python dependencies
```
