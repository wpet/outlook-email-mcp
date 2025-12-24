"""
Tests for the api module.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests
from src.api import graph_get, graph_post, parallel_fetch, graph_batch, batch_get_messages


class TestGraphGet:
    """Tests for graph_get function."""

    def test_graph_get_success(self, mock_graph_response):
        """Test successful GET request."""
        mock_graph_response.json.return_value = {"value": [{"id": "1"}]}

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.get", return_value=mock_graph_response):
                result = graph_get("/users/test@example.com/messages")

        assert result == {"value": [{"id": "1"}]}

    def test_graph_get_with_params(self, mock_graph_response):
        """Test GET request with query parameters."""
        mock_graph_response.json.return_value = {"value": []}

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.get", return_value=mock_graph_response) as mock_get:
                result = graph_get("/users/test@example.com/messages", {"$top": 10})

        # Verify params were passed
        call_args = mock_get.call_args
        assert call_args.kwargs["params"] == {"$top": 10}

    def test_graph_get_no_token(self):
        """Test handling when no token is available."""
        with patch("src.api.get_access_token", return_value=None):
            result = graph_get("/users/test@example.com/messages")

        assert result is None

    def test_graph_get_timeout(self):
        """Test handling of request timeout."""
        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
                result = graph_get("/users/test@example.com/messages")

        assert result is None

    def test_graph_get_error(self, mock_graph_error_response):
        """Test handling of API error response."""
        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.get", return_value=mock_graph_error_response):
                result = graph_get("/users/test@example.com/messages")

        assert result is None

    def test_graph_get_connection_error(self):
        """Test handling of connection error."""
        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.get", side_effect=requests.exceptions.ConnectionError("No connection")):
                result = graph_get("/users/test@example.com/messages")

        assert result is None


class TestGraphPost:
    """Tests for graph_post function."""

    def test_graph_post_success(self):
        """Test successful POST request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"responses": []}

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response):
                result = graph_post("/$batch", {"requests": []})

        assert result == {"responses": []}

    def test_graph_post_201_created(self):
        """Test POST with 201 Created response."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "new_resource"}

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response):
                result = graph_post("/resource", {"data": "value"})

        assert result == {"id": "new_resource"}

    def test_graph_post_no_token(self):
        """Test handling when no token is available."""
        with patch("src.api.get_access_token", return_value=None):
            result = graph_post("/$batch", {"requests": []})

        assert result is None


class TestParallelFetch:
    """Tests for parallel_fetch function."""

    def test_parallel_fetch(self):
        """Test parallel fetching of multiple items."""
        def fetch_fn(item):
            return f"result_{item}"

        items = [1, 2, 3, 4, 5]
        results = parallel_fetch(fetch_fn, items)

        assert len(results) == 5
        assert results == ["result_1", "result_2", "result_3", "result_4", "result_5"]

    def test_parallel_fetch_empty(self):
        """Test parallel fetch with empty list."""
        def fetch_fn(item):
            return item

        results = parallel_fetch(fetch_fn, [])
        assert results == []

    def test_parallel_fetch_partial_failure(self):
        """Test parallel fetch with some failures."""
        def fetch_fn(item):
            if item == 3:
                raise ValueError("Item 3 failed")
            return f"result_{item}"

        items = [1, 2, 3, 4, 5]
        results = parallel_fetch(fetch_fn, items)

        assert results[0] == "result_1"
        assert results[1] == "result_2"
        assert results[2] is None  # Failed item
        assert results[3] == "result_4"
        assert results[4] == "result_5"

    def test_parallel_fetch_max_workers(self):
        """Test parallel fetch respects max workers."""
        call_count = []

        def fetch_fn(item):
            call_count.append(item)
            return item

        items = [1, 2, 3]
        results = parallel_fetch(fetch_fn, items, max_workers=2)

        assert results == [1, 2, 3]
        assert len(call_count) == 3

    def test_parallel_fetch_preserves_order(self):
        """Test that results preserve input order."""
        import time

        def fetch_fn(item):
            # Simulate varying response times
            time.sleep(0.01 * (5 - item))  # First items take longer
            return item * 10

        items = [1, 2, 3, 4, 5]
        results = parallel_fetch(fetch_fn, items)

        # Results should be in original order despite completion order
        assert results == [10, 20, 30, 40, 50]


class TestGraphBatch:
    """Tests for graph_batch function."""

    def test_graph_batch_success(self):
        """Test successful batch request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "responses": [
                {"id": "1", "status": 200, "body": {"subject": "Email 1"}},
                {"id": "2", "status": 200, "body": {"subject": "Email 2"}}
            ]
        }

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response):
                requests_list = [
                    {"id": "1", "method": "GET", "url": "/users/test/messages/1"},
                    {"id": "2", "method": "GET", "url": "/users/test/messages/2"}
                ]
                results = graph_batch(requests_list)

        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[0]["status"] == 200
        assert results[0]["body"]["subject"] == "Email 1"

    def test_graph_batch_empty(self):
        """Test batch with empty request list."""
        results = graph_batch([])
        assert results == []

    def test_graph_batch_exceeds_limit(self):
        """Test batch with more than 20 requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"responses": []}

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response) as mock_post:
                # Create 25 requests
                requests_list = [
                    {"id": str(i), "method": "GET", "url": f"/messages/{i}"}
                    for i in range(25)
                ]
                graph_batch(requests_list)

        # Verify only 20 were sent
        call_args = mock_post.call_args
        sent_requests = call_args.kwargs["json"]["requests"]
        assert len(sent_requests) == 20

    def test_graph_batch_failure(self):
        """Test batch request failure."""
        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", side_effect=requests.exceptions.Timeout()):
                requests_list = [
                    {"id": "1", "method": "GET", "url": "/messages/1"}
                ]
                results = graph_batch(requests_list)

        assert len(results) == 1
        assert results[0]["status"] == 0
        assert "error" in results[0]["body"]


class TestBatchGetMessages:
    """Tests for batch_get_messages function."""

    def test_batch_get_messages(self):
        """Test fetching multiple messages via batch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "responses": [
                {"id": "0", "status": 200, "body": {"id": "msg1", "subject": "Test 1"}},
                {"id": "1", "status": 200, "body": {"id": "msg2", "subject": "Test 2"}}
            ]
        }

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response):
                urls = ["/users/test/messages/msg1", "/users/test/messages/msg2"]
                results = batch_get_messages(urls)

        assert len(results) == 2
        assert results[0]["id"] == "msg1"
        assert results[1]["id"] == "msg2"

    def test_batch_get_messages_partial_failure(self):
        """Test batch messages with some failures."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "responses": [
                {"id": "0", "status": 200, "body": {"id": "msg1"}},
                {"id": "1", "status": 404, "body": {"error": "Not found"}}
            ]
        }

        with patch("src.api.get_access_token", return_value="test_token"):
            with patch("requests.post", return_value=mock_response):
                urls = ["/messages/msg1", "/messages/msg2"]
                results = batch_get_messages(urls)

        assert results[0] == {"id": "msg1"}
        assert results[1] is None  # Failed request

    def test_batch_get_messages_empty(self):
        """Test batch messages with empty list."""
        results = batch_get_messages([])
        assert results == []
