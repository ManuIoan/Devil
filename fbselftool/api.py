"""A thin wrapper around Facebook's official Graph API.

Only read operations that the current official API genuinely supports for a
user's *own* account are implemented here. Nothing in this module targets any
account other than the one that owns the supplied access token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import requests

# Pin a specific, current Graph API version so behaviour is predictable.
# Bump this deliberately after checking the Graph API changelog.
GRAPH_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

# A sensible timeout so the CLI never hangs forever on a bad network.
REQUEST_TIMEOUT = 30


class GraphAPIError(RuntimeError):
    """Raised when the Graph API returns an error payload or an HTTP error."""

    def __init__(self, message: str, *, code: Optional[int] = None,
                 type_: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.type = type_
        self.http_status = http_status


@dataclass
class Post:
    """A single post from the user's own feed."""

    id: str
    created_time: Optional[str] = None
    message: Optional[str] = None
    story: Optional[str] = None
    permalink_url: Optional[str] = None

    @property
    def summary(self) -> str:
        text = self.message or self.story or "(no text — media or shared content)"
        text = " ".join(text.split())  # collapse whitespace/newlines
        if len(text) > 80:
            text = text[:77] + "..."
        return text


class GraphAPIClient:
    """Minimal Graph API client scoped to the token owner's own account.

    The access token is held only in memory for the lifetime of the client.
    It is never written to disk and never logged.
    """

    def __init__(self, access_token: str, *, session: Optional[requests.Session] = None):
        if not access_token or not access_token.strip():
            raise ValueError("An access token is required.")
        self._token = access_token.strip()
        self._session = session or requests.Session()

    # -- internal helpers -------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params["access_token"] = self._token
        url = path if path.startswith("http") else f"{BASE_URL}/{path.lstrip('/')}"
        try:
            resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise GraphAPIError(f"Network error talking to the Graph API: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError:
            raise GraphAPIError(
                f"Graph API returned a non-JSON response (HTTP {resp.status_code}).",
                http_status=resp.status_code,
            )

        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            raise GraphAPIError(
                err.get("message", "Unknown Graph API error."),
                code=err.get("code"),
                type_=err.get("type"),
                http_status=resp.status_code,
            )

        if not resp.ok:
            raise GraphAPIError(
                f"Graph API request failed with HTTP {resp.status_code}.",
                http_status=resp.status_code,
            )
        return payload

    # -- public, read-only operations on the token owner's own account ----

    def me(self) -> Dict[str, Any]:
        """Return the token owner's basic public profile (id + name)."""
        return self._get("me", {"fields": "id,name"})

    def permissions(self) -> List[Dict[str, str]]:
        """Return the list of permissions granted to this token.

        Each entry looks like {"permission": "user_posts", "status": "granted"}.
        Useful for the user to verify their token has the scopes they expect.
        """
        data = self._get("me/permissions")
        return list(data.get("data", []))

    def friend_summary(self) -> Dict[str, Any]:
        """Return the friend-count summary for the token owner.

        NOTE: the Graph API only ever exposes a *count* here, and only counts
        friends who also use the same app. There is no official way to list,
        add, or remove friends. See the README for details.
        """
        data = self._get("me/friends", {"summary": "true", "limit": 0})
        summary = data.get("summary", {})
        return {
            "total_count": summary.get("total_count"),
            "app_friends_returned": len(data.get("data", [])),
        }

    def iter_posts(self, *, page_limit: int = 25, max_pages: int = 20) -> Iterator[Post]:
        """Yield the token owner's own posts, newest first (read-only).

        Requires the `user_posts` permission. Pagination is followed until
        there are no more pages or `max_pages` is reached, whichever comes
        first, so a very active account can't spin forever.
        """
        fields = "id,created_time,message,story,permalink_url"
        payload = self._get("me/posts", {"fields": fields, "limit": page_limit})
        pages = 0
        while True:
            for item in payload.get("data", []):
                yield Post(
                    id=item.get("id", ""),
                    created_time=item.get("created_time"),
                    message=item.get("message"),
                    story=item.get("story"),
                    permalink_url=item.get("permalink_url"),
                )
            pages += 1
            next_url = payload.get("paging", {}).get("next")
            if not next_url or pages >= max_pages:
                break
            # The `next` URL already carries the token and cursor.
            payload = self._get(next_url)
