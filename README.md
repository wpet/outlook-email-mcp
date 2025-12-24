# Outlook Email MCP Server

An MCP (Model Context Protocol) server that enables Claude Code to search and analyze Outlook emails via Microsoft Graph API.

## Features

- **Search emails** - Search by sender, recipient, subject, date
- **Get conversations** - Retrieve complete email threads
- **Read email body** - Full email content (text or HTML)
- **List attachments** - View email attachments

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/wpet/outlook-email-mcp.git
cd outlook-email-mcp
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Azure credentials

```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials:

```env
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TARGET_USER=user@domain.com
```

### 5. Configure Claude Code

Copy `.mcp.json.example` to `.mcp.json` and adjust the paths:

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json`:

```json
{
  "mcpServers": {
    "outlook-email": {
      "command": "python3",
      "args": ["/full/path/to/outlook-email-mcp/mcp_server/server.py"],
      "env": {
        "PYTHONPATH": "/full/path/to/outlook-email-mcp"
      }
    }
  }
}
```

### 6. Restart Claude Code

After configuration, restart Claude Code to load the MCP server.

## Azure App Registration

### Step 1: Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Search for "App registrations"
3. Click "New registration"
4. Name: `outlook-email-mcp`
5. Account type: "Single tenant"
6. Click "Register"

### Step 2: Note the IDs

- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Step 3: Create Client Secret

1. Go to "Certificates & secrets"
2. Click "New client secret"
3. Copy the value → `AZURE_CLIENT_SECRET`

### Step 4: Configure API Permissions

1. Go to "API permissions"
2. Click "Add a permission"
3. Choose "Microsoft Graph"
4. Choose "Application permissions"
5. Add:
   - `Mail.Read` - Read emails
   - `User.Read.All` - Look up users
6. Click "Grant admin consent"

## Usage

After installation, these tools are available in Claude Code:

| Tool | Description |
|------|-------------|
| `search_emails` | Search emails with filters (from, to, subject, date) |
| `get_conversation` | Retrieve complete email thread |
| `get_email_body` | Read full email content |
| `list_attachments` | View attachments of an email |

### Examples

```
"Search all emails from jan@example.com about invoices"

"Get the conversation about project X"

"What attachments are in the last email from finance?"
```

## Verification

Test if the MCP server is configured correctly:

```bash
# In Claude Code
/mcp
```

You should see `outlook-email` in the list of active servers.

## Files

```
outlook-email-mcp/
├── src/
│   └── graph_client.py      # Microsoft Graph API client
├── mcp_server/
│   └── server.py            # MCP server implementation
├── .env.example             # Template for credentials
├── .mcp.json.example        # Template for Claude Code config
└── requirements.txt         # Python dependencies
```

## Security

- Credentials are loaded from `.env` (not in git)
- Request timeout: 30 seconds
- Token caching with expiry validation
- OData injection prevention on conversation_id

## License

MIT
