# Microsoft Entra ID App Registration Setup

This guide walks you through creating an app registration for accessing Outlook email via Microsoft Graph API with delegated permissions.

## Prerequisites

- Access to [Azure Portal](https://portal.azure.com)
- Sufficient permissions to create app registrations in your tenant

## Step 1: Create App Registration

1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations** → **New registration**

2. Fill in the following:
   - **Name**: `outlook-email-mcp` (or your preferred name)
   - **Supported account types**: Select "Accounts in this organizational directory only" (single tenant)
   - **Redirect URI**:
     - Platform: **Public client/native (mobile & desktop)**
     - URI: `http://localhost:8400`

3. Click **Register**

4. On the overview page, note down:
   - **Application (client) ID**
   - **Directory (tenant) ID**

## Step 2: Configure API Permissions

1. In your app registration, go to **API permissions** → **Add a permission**

2. Select **Microsoft Graph** → **Delegated permissions**

3. Add the following permissions:
   - `Mail.Read` — Read user mail
   - `Mail.ReadWrite` — Read and write user mail
   - `Mail.Send` — Send mail as user
   - `offline_access` — Maintain access to data (for refresh tokens)
   - `User.Read` — Sign in and read user profile

4. Click **Add permissions**

5. Optional: Click **Grant admin consent for [tenant]** if you have admin rights and want to pre-approve for all users

## Step 3: Configure Authentication Settings

1. Go to **Authentication**

2. Verify that under **Mobile and desktop applications** the redirect URI `http://localhost:8400` is listed

3. Click the **Advanced settings** tab (or scroll down to find it)

4. Set **Allow public client flows** to **Yes**

5. Click **Save**

## Step 4: Configure Environment

Create a `.env` file in your project root with the credentials from Step 1:

```env
AZURE_CLIENT_ID=your-application-client-id
AZURE_TENANT_ID=your-directory-tenant-id
```

## Verification

Run the application to verify the setup:

```bash
python src/outlook_email.py
```

On first run, a browser window will open for authentication. After successful login, the application will display your profile information and recent emails.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `AADSTS50011: Reply URL mismatch` | Verify redirect URI matches exactly: `http://localhost:8400` |
| `AADSTS65001: User or admin has not consented` | Grant admin consent or have user approve permissions on first login |
| `AADSTS7000218: Request body must contain client_assertion or client_secret` | Ensure "Allow public client flows" is set to Yes |
