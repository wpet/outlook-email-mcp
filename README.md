# Outlook Email MCP Server

An MCP (Model Context Protocol) server that enables Claude Code to search and analyze Outlook emails via Microsoft Graph API.

## Features

- **Search emails** - Search by sender, recipient, subject, date
- **Get conversations** - Retrieve complete email threads
- **Bulk conversations** - Fetch multiple conversations in parallel
- **Read email body** - Full email content (text or HTML)
- **List attachments** - View email attachments

### Performance

- **Caching** - Email bodies, conversations, and attachments are cached for faster repeated access
- **Parallel requests** - Bulk operations execute API calls concurrently

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

### Step 3: Configure as Public Client

1. Go to "Authentication"
2. Click "Add a platform"
3. Choose "Mobile and desktop applications"
4. Select the redirect URI: `https://login.microsoftonline.com/common/oauth2/nativeclient`
5. Under "Advanced settings", set **Allow public client flows** to **Yes**
6. Click "Save"

### Step 4: Configure API Permissions

1. Go to "API permissions"
2. Click "Add a permission"
3. Choose "Microsoft Graph"
4. Choose "Delegated permissions"
5. Add:
   - `Mail.Read` - Read user mail
   - `User.Read` - Sign in and read user profile
6. Click "Add permissions"

Note: Admin consent is not required for delegated permissions.

### Step 5: First-time Login

On first use, a browser window will open for authentication.
After login, the token is cached in `token_cache.json` for subsequent use.

## Usage

After installation, these tools are available in Claude Code:

| Tool | Description |
|------|-------------|
| `search_emails` | Search emails with filters (from, to, subject, date) |
| `get_conversation` | Retrieve complete email thread |
| `get_conversations_bulk` | Fetch multiple conversations in parallel |
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

## Project Structure

```
outlook-email-mcp/
├── src/
│   ├── api.py               # Microsoft Graph API client
│   ├── auth.py              # Azure AD authentication
│   ├── cache.py             # Response caching
│   ├── config.py            # Configuration management
│   ├── emails.py            # Email operations
│   └── parsing.py           # Email parsing utilities
├── mcp_server/
│   └── server.py            # MCP server implementation
├── tests/
│   ├── test_api.py          # API tests
│   ├── test_auth.py         # Authentication tests
│   ├── test_cache.py        # Cache tests
│   ├── test_emails.py       # Email operations tests
│   ├── test_parsing.py      # Parsing tests
│   └── test_server.py       # Server tests
├── .env.example             # Template for credentials
├── .mcp.json.example        # Template for Claude Code config
└── requirements.txt         # Python dependencies
```

## Security

- Credentials are loaded from `.env` (not in git)
- Token cached in `token_cache.json` (not in git)
- Request timeout: 30 seconds
- OData injection prevention on conversation_id

## License

MIT
