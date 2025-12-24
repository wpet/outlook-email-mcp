# Outlook Email MCP Server

Een MCP (Model Context Protocol) server waarmee Claude Code direct Outlook emails kan doorzoeken en analyseren via Microsoft Graph API.

## Features

- **Email zoeken** - Zoek op afzender, ontvanger, onderwerp, datum
- **Conversatie ophalen** - Haal complete email threads op
- **Email body lezen** - Volledige email inhoud (text of HTML)
- **Bijlagen bekijken** - Lijst attachments van emails

## Installatie

### 1. Clone de repository

```bash
git clone https://github.com/wpet/outlook-email-mcp.git
cd outlook-email-mcp
```

### 2. Maak virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# of: venv\Scripts\activate  # Windows
```

### 3. Installeer dependencies

```bash
pip install -r requirements.txt
```

### 4. Configureer Azure credentials

```bash
cp .env.example .env
```

Edit `.env` met je Azure credentials:

```env
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TARGET_USER=user@domain.com
```

### 5. Configureer Claude Code

Kopieer `.mcp.json.example` naar `.mcp.json` en pas de paden aan:

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json`:

```json
{
  "mcpServers": {
    "outlook-email": {
      "command": "python3",
      "args": ["/volledig/pad/naar/outlook-email-mcp/mcp_server/server.py"],
      "env": {
        "PYTHONPATH": "/volledig/pad/naar/outlook-email-mcp"
      }
    }
  }
}
```

### 6. Herstart Claude Code

Na configuratie, herstart Claude Code om de MCP server te laden.

## Azure App Registration

### Stap 1: Maak App Registration

1. Ga naar [Azure Portal](https://portal.azure.com)
2. Zoek naar "App registrations"
3. Klik "New registration"
4. Naam: `outlook-email-mcp`
5. Account type: "Single tenant"
6. Klik "Register"

### Stap 2: Noteer IDs

- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Stap 3: Maak Client Secret

1. Ga naar "Certificates & secrets"
2. Klik "New client secret"
3. Kopieer de waarde → `AZURE_CLIENT_SECRET`

### Stap 4: Configureer API Permissions

1. Ga naar "API permissions"
2. Klik "Add a permission"
3. Kies "Microsoft Graph"
4. Kies "Application permissions"
5. Voeg toe:
   - `Mail.Read` - Emails lezen
   - `User.Read.All` - Gebruikers opzoeken
6. Klik "Grant admin consent"

## Gebruik

Na installatie zijn deze tools beschikbaar in Claude Code:

| Tool | Beschrijving |
|------|-------------|
| `search_emails` | Zoek emails met filters (from, to, subject, date) |
| `get_conversation` | Haal complete email thread op |
| `get_email_body` | Lees volledige email inhoud |
| `list_attachments` | Bekijk bijlagen van een email |

### Voorbeelden

```
"Zoek alle emails van jan@example.com over facturen"

"Haal de conversatie op over project X"

"Welke bijlagen zitten er in de laatste email van finance?"
```

## Verificatie

Test of de MCP server correct is geconfigureerd:

```bash
# In Claude Code
/mcp
```

Je zou `outlook-email` moeten zien in de lijst van actieve servers.

## Bestanden

```
outlook-email-mcp/
├── src/
│   └── graph_client.py      # Microsoft Graph API client
├── mcp_server/
│   └── server.py            # MCP server implementatie
├── .env.example             # Template voor credentials
├── .mcp.json.example        # Template voor Claude Code config
└── requirements.txt         # Python dependencies
```

## Security

- Credentials worden geladen uit `.env` (niet in git)
- Request timeout: 30 seconden
- Token caching met expiry validatie
- OData injection preventie op conversation_id

## Licentie

MIT
