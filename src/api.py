"""
API module for Microsoft Graph API requests.
Provides HTTP helpers, parallel fetching, and batch requests.
"""

import logging
from typing import Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import GRAPH_ENDPOINT, REQUEST_TIMEOUT, MAX_PARALLEL_REQUESTS
from .auth import get_access_token

logger = logging.getLogger(__name__)


# =============================================================================
# HTTP HELPERS
# =============================================================================

def graph_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """
    Make a GET request to Graph API.

    Args:
        endpoint: API endpoint (without base URL)
        params: Query parameters

    Returns:
        JSON response or None on error
    """
    token = get_access_token()
    if not token:
        return None

    url = f"{GRAPH_ENDPOINT}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout after {REQUEST_TIMEOUT}s: {endpoint}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"API error {response.status_code}: {response.text[:200]}")
        return None


def graph_post(endpoint: str, json_data: dict = None) -> Optional[dict]:
    """
    Make a POST request to Graph API.

    Args:
        endpoint: API endpoint (without base URL)
        json_data: JSON body

    Returns:
        JSON response or None on error
    """
    token = get_access_token()
    if not token:
        return None

    url = f"{GRAPH_ENDPOINT}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout after {REQUEST_TIMEOUT}s: {endpoint}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

    if response.status_code in (200, 201):
        return response.json()
    else:
        logger.error(f"API error {response.status_code}: {response.text[:200]}")
        return None


# =============================================================================
# PARALLEL REQUESTS
# =============================================================================

def parallel_fetch(fetch_fn: Callable[[Any], Any], items: list, max_workers: int = None) -> list:
    """
    Execute fetch function in parallel for multiple items.

    Args:
        fetch_fn: Function to call for each item (takes single item as arg)
        items: List of items to process
        max_workers: Max concurrent threads (default: MAX_PARALLEL_REQUESTS)

    Returns:
        List of results in same order as items
    """
    if not items:
        return []

    max_workers = max_workers or MAX_PARALLEL_REQUESTS
    max_workers = min(max_workers, len(items))  # Don't create more workers than items

    results = [None] * len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with their index
        future_to_index = {
            executor.submit(fetch_fn, item): i
            for i, item in enumerate(items)
        }

        # Collect results as they complete
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Parallel fetch error for item {index}: {e}")
                results[index] = None

    return results


# =============================================================================
# BATCH REQUESTS
# =============================================================================

def graph_batch(requests_list: list[dict]) -> list[dict]:
    """
    Execute multiple Graph API requests in a single batch call.

    Microsoft Graph supports batching up to 20 requests per call.
    Each request in the batch is executed independently.

    Args:
        requests_list: List of request dicts with keys:
            - id: Unique identifier for the request
            - method: HTTP method (GET, POST, etc.)
            - url: Relative URL (e.g., "/users/{user}/messages/{id}")

    Returns:
        List of response dicts with keys:
            - id: Request identifier
            - status: HTTP status code
            - body: Response body (parsed JSON)

    Example:
        >>> requests = [
        ...     {"id": "1", "method": "GET", "url": "/users/user@example.com/messages/msg1"},
        ...     {"id": "2", "method": "GET", "url": "/users/user@example.com/messages/msg2"},
        ... ]
        >>> responses = graph_batch(requests)
        >>> for resp in responses:
        ...     print(f"Request {resp['id']}: {resp['status']}")
    """
    if not requests_list:
        return []

    if len(requests_list) > 20:
        logger.warning(f"Batch request exceeds 20 limit ({len(requests_list)}), truncating")
        requests_list = requests_list[:20]

    # Build batch request body
    batch_body = {
        "requests": requests_list
    }

    # Execute batch request
    response = graph_post("/$batch", batch_body)

    if not response:
        # Return error for all requests
        return [
            {"id": req.get("id", str(i)), "status": 0, "body": {"error": "Batch request failed"}}
            for i, req in enumerate(requests_list)
        ]

    # Parse responses
    responses = response.get("responses", [])

    # Sort responses by id to maintain order
    id_to_response = {resp.get("id"): resp for resp in responses}

    results = []
    for req in requests_list:
        req_id = req.get("id", "")
        if req_id in id_to_response:
            resp = id_to_response[req_id]
            results.append({
                "id": req_id,
                "status": resp.get("status", 0),
                "body": resp.get("body", {})
            })
        else:
            results.append({
                "id": req_id,
                "status": 0,
                "body": {"error": "Response not found"}
            })

    return results


def batch_get_messages(message_urls: list[str]) -> list[Optional[dict]]:
    """
    Fetch multiple messages using batch API.

    Args:
        message_urls: List of message endpoint URLs (relative to Graph API base)

    Returns:
        List of message dicts (or None for failed requests)
    """
    if not message_urls:
        return []

    # Build batch requests
    requests_list = [
        {"id": str(i), "method": "GET", "url": url}
        for i, url in enumerate(message_urls)
    ]

    # Execute batch
    responses = graph_batch(requests_list)

    # Extract bodies, return None for failed requests
    results = []
    for resp in responses:
        if resp.get("status") == 200:
            results.append(resp.get("body"))
        else:
            results.append(None)

    return results
