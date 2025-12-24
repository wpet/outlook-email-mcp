"""
Tests for the auth module.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestGetAccessToken:
    """Tests for token acquisition."""

    def test_get_access_token_from_cache(self, mock_msal_app):
        """Test token acquisition from cache."""
        mock_cache = MagicMock()
        mock_cache.deserialize = MagicMock()
        mock_cache.has_state_changed = False

        with patch("src.auth.msal.PublicClientApplication", return_value=mock_msal_app):
            with patch("src.auth.msal.SerializableTokenCache", return_value=mock_cache):
                with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
                    mock_file.exists.return_value = True
                    mock_file.read_text.return_value = "{}"
                    with patch("src.auth.CLIENT_ID", "test-id"):
                        with patch("src.auth.TENANT_ID", "test-tenant"):
                            from src.auth import get_access_token
                            token = get_access_token()

        assert token == "test_token_123"
        mock_msal_app.acquire_token_silent.assert_called_once()

    def test_get_access_token_interactive(self):
        """Test interactive token acquisition when no cached token."""
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []  # No cached accounts
        mock_app.acquire_token_interactive.return_value = {
            "access_token": "interactive_token",
            "expires_in": 3600
        }

        mock_cache = MagicMock()
        mock_cache.deserialize = MagicMock()
        mock_cache.has_state_changed = True
        mock_cache.serialize.return_value = "{}"

        with patch("src.auth.msal.PublicClientApplication", return_value=mock_app):
            with patch("src.auth.msal.SerializableTokenCache", return_value=mock_cache):
                with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
                    mock_file.exists.return_value = False
                    with patch("src.auth.CLIENT_ID", "test-id"):
                        with patch("src.auth.TENANT_ID", "test-tenant"):
                            from src.auth import get_access_token
                            token = get_access_token()

        assert token == "interactive_token"
        mock_app.acquire_token_interactive.assert_called_once()

    def test_get_access_token_missing_credentials(self):
        """Test handling of missing credentials."""
        with patch("src.auth.CLIENT_ID", None):
            with patch("src.auth.TENANT_ID", "test-tenant"):
                from src.auth import get_access_token
                token = get_access_token()

        assert token is None

    def test_get_access_token_auth_failure(self):
        """Test handling of authentication failure."""
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []
        mock_app.acquire_token_interactive.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client"
        }

        mock_cache = MagicMock()
        mock_cache.deserialize = MagicMock()
        mock_cache.has_state_changed = False

        with patch("src.auth.msal.PublicClientApplication", return_value=mock_app):
            with patch("src.auth.msal.SerializableTokenCache", return_value=mock_cache):
                with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
                    mock_file.exists.return_value = False
                    with patch("src.auth.CLIENT_ID", "test-id"):
                        with patch("src.auth.TENANT_ID", "test-tenant"):
                            from src.auth import get_access_token
                            token = get_access_token()

        assert token is None


class TestClearTokenCache:
    """Tests for token cache clearing."""

    def test_clear_token_cache_exists(self):
        """Test clearing existing token cache file."""
        with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
            mock_file.exists.return_value = True
            from src.auth import clear_token_cache
            clear_token_cache()
            mock_file.unlink.assert_called_once()

    def test_clear_token_cache_not_exists(self):
        """Test clearing when no cache file exists."""
        with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
            mock_file.exists.return_value = False
            from src.auth import clear_token_cache
            clear_token_cache()
            mock_file.unlink.assert_not_called()


class TestIsAuthenticated:
    """Tests for authentication status checking."""

    def test_is_authenticated_true(self, mock_msal_app):
        """Test that valid cached token returns True."""
        mock_cache = MagicMock()
        mock_cache.deserialize = MagicMock()

        with patch("src.auth.msal.PublicClientApplication", return_value=mock_msal_app):
            with patch("src.auth.msal.SerializableTokenCache", return_value=mock_cache):
                with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
                    mock_file.exists.return_value = True
                    mock_file.read_text.return_value = "{}"
                    with patch("src.auth.CLIENT_ID", "test-id"):
                        with patch("src.auth.TENANT_ID", "test-tenant"):
                            from src.auth import is_authenticated
                            assert is_authenticated() is True

    def test_is_authenticated_no_cache_file(self):
        """Test that missing cache file returns False."""
        with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
            mock_file.exists.return_value = False
            from src.auth import is_authenticated
            assert is_authenticated() is False

    def test_is_authenticated_no_accounts(self):
        """Test that no cached accounts returns False."""
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        mock_cache = MagicMock()
        mock_cache.deserialize = MagicMock()

        with patch("src.auth.msal.PublicClientApplication", return_value=mock_app):
            with patch("src.auth.msal.SerializableTokenCache", return_value=mock_cache):
                with patch("src.auth.TOKEN_CACHE_FILE") as mock_file:
                    mock_file.exists.return_value = True
                    mock_file.read_text.return_value = "{}"
                    with patch("src.auth.CLIENT_ID", "test-id"):
                        with patch("src.auth.TENANT_ID", "test-tenant"):
                            from src.auth import is_authenticated
                            assert is_authenticated() is False
