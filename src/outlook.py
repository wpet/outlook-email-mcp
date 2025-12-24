"""
Outlook Email Client using Microsoft Graph API
Uses delegated permissions (interactive login)
"""

import os
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

# Load .env from project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
TENANT_ID = os.environ["AZURE_TENANT_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read", "Mail.Send", "User.Read"]
REDIRECT_URI = "http://localhost:8400"
TOKEN_CACHE_FILE = PROJECT_ROOT / "token_cache.json"

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def load_cache() -> msal.SerializableTokenCache:
    """Load token cache from disk."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text())
    return cache


def save_cache(cache: msal.SerializableTokenCache) -> None:
    """Save token cache to disk."""
    if cache.has_state_changed:
        TOKEN_CACHE_FILE.write_text(cache.serialize())


def get_access_token() -> str | None:
    """Obtain access token via interactive login or cache."""
    cache = load_cache()

    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )

    # Try token from cache first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            save_cache(cache)
            return result["access_token"]

    # Otherwise interactive login
    print("Opening browser for login...")
    result = app.acquire_token_interactive(scopes=SCOPES)

    save_cache(cache)

    if "access_token" in result:
        return result["access_token"]

    print(f"Authentication error: {result.get('error_description', result)}")
    return None


def get_headers(token: str) -> dict:
    """Create headers for Graph API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_me(token: str) -> dict | None:
    """Get profile info of logged in user."""
    response = requests.get(f"{GRAPH_BASE_URL}/me", headers=get_headers(token))
    if response.ok:
        return response.json()
    print(f"Error: {response.status_code} - {response.text}")
    return None


def get_messages(token: str, top: int = 10, folder: str = "inbox") -> list[dict]:
    """
    Retrieve emails from a folder.

    Args:
        token: Access token
        top: Number of messages to retrieve
        folder: Folder name (inbox, sentitems, drafts, etc.)
    """
    url = f"{GRAPH_BASE_URL}/me/mailFolders/{folder}/messages"
    params = {
        "$top": top,
        "$select": "subject,from,receivedDateTime,isRead,bodyPreview",
        "$orderby": "receivedDateTime DESC",
    }

    response = requests.get(url, headers=get_headers(token), params=params)
    if response.ok:
        return response.json().get("value", [])
    print(f"Error: {response.status_code} - {response.text}")
    return []


def get_message_body(token: str, message_id: str) -> dict | None:
    """Retrieve full email including body."""
    url = f"{GRAPH_BASE_URL}/me/messages/{message_id}"
    params = {"$select": "subject,from,toRecipients,receivedDateTime,body"}

    response = requests.get(url, headers=get_headers(token), params=params)
    if response.ok:
        return response.json()
    print(f"Error: {response.status_code} - {response.text}")
    return None


def send_email(
    token: str, to: str, subject: str, body: str, content_type: str = "Text"
) -> bool:
    """
    Send an email.

    Args:
        token: Access token
        to: Recipient email address
        subject: Subject
        body: Email content
        content_type: "Text" or "HTML"
    """
    url = f"{GRAPH_BASE_URL}/me/sendMail"

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": content_type,
                "content": body,
            },
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
    }

    response = requests.post(url, headers=get_headers(token), json=payload)
    if response.status_code == 202:
        print(f"Email sent to {to}")
        return True
    print(f"Error: {response.status_code} - {response.text}")
    return False


def main():
    """Demo of the functionality."""
    print("Outlook Email Client")
    print("=" * 40)

    # Authentication
    token = get_access_token()
    if not token:
        print("Could not obtain access token.")
        return

    # Show logged in user
    me = get_me(token)
    if me:
        print(f"\nLogged in as: {me.get('displayName')} ({me.get('mail')})")

    # Show latest emails
    print("\nLatest 5 emails in inbox:")
    print("-" * 40)

    messages = get_messages(token, top=5)
    for msg in messages:
        from_name = msg.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = msg.get("subject", "(geen onderwerp)")
        received = msg.get("receivedDateTime", "")[:16].replace("T", " ")
        read_status = "✓" if msg.get("isRead") else "•"

        print(f"{read_status} {received} | {from_name}")
        print(f"  {subject}")
        print()


if __name__ == "__main__":
    main()
