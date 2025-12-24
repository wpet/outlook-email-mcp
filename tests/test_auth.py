"""
Tests for the auth module.
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from src.auth import get_access_token, clear_token_cache, is_token_valid


class TestGetAccessToken:
    """Tests for token acquisition."""

    def test_get_access_token_success(self, mock_msal_app):
        """Test successful token acquisition."""
        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_msal_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        token = get_access_token()

        assert token == "test_token_123"
        mock_msal_app.acquire_token_for_client.assert_called_once()

    def test_get_access_token_cached(self, mock_msal_app):
        """Test that cached token is returned without API call."""
        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_msal_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        # First call - should hit MSAL
                        token1 = get_access_token()
                        # Second call - should use cache
                        token2 = get_access_token()

        assert token1 == token2
        # Should only be called once due to caching
        assert mock_msal_app.acquire_token_for_client.call_count == 1

    def test_get_access_token_expired_refresh(self):
        """Test that expired token triggers refresh."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "new_token",
            "expires_in": 3600
        }

        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        with patch("src.auth._token_expiry", time.time() - 100):
                            with patch("src.auth._token_cache", "old_token"):
                                # Token is expired, should fetch new one
                                token = get_access_token()

        assert token == "new_token"

    def test_get_access_token_missing_credentials(self):
        """Test handling of missing credentials."""
        with patch("src.auth.CLIENT_ID", None):
            with patch("src.auth.TENANT_ID", "test-tenant"):
                with patch("src.auth.CLIENT_SECRET", "test-secret"):
                    clear_token_cache()
                    token = get_access_token()

        assert token is None

    def test_get_access_token_auth_failure(self):
        """Test handling of authentication failure."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }

        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        clear_token_cache()
                        token = get_access_token()

        assert token is None


class TestClearTokenCache:
    """Tests for token cache clearing."""

    def test_clear_token_cache(self, mock_msal_app):
        """Test clearing the token cache."""
        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_msal_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        # Get a token first
                        get_access_token()

                        # Clear cache
                        clear_token_cache()

                        # Next call should hit MSAL again
                        get_access_token()

        # Should be called twice (once before clear, once after)
        assert mock_msal_app.acquire_token_for_client.call_count == 2


class TestIsTokenValid:
    """Tests for token validity checking."""

    def test_is_token_valid_true(self, mock_msal_app):
        """Test that valid token returns True."""
        with patch("src.auth.msal.ConfidentialClientApplication", return_value=mock_msal_app):
            with patch("src.auth.CLIENT_ID", "test-id"):
                with patch("src.auth.TENANT_ID", "test-tenant"):
                    with patch("src.auth.CLIENT_SECRET", "test-secret"):
                        get_access_token()
                        assert is_token_valid() is True

    def test_is_token_valid_no_token(self):
        """Test that no token returns False."""
        clear_token_cache()
        assert is_token_valid() is False

    def test_is_token_valid_expired(self):
        """Test that expired token returns False."""
        with patch("src.auth._token_cache", "some_token"):
            with patch("src.auth._token_expiry", time.time() - 100):
                assert is_token_valid() is False
