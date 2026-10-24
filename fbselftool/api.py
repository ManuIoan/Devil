"""A thin wrapper around Facebook's official Graph API.

Only operations that the current official API genuinely supports are
implemented here, and everything is scoped to the account (or the Pages)
that the supplied access token controls. Nothing here targets any other
person's account or data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    # Aggregate engagement on the user's own post. Only counts are collected
    # (never the identities of commenters/reactors — that would be other
    # people's data, and the API restricts it anyway).
    comment_count: Optional[int] = None
    reaction_count: Optional[int] = None

    @property
    def summary(self) -> str:
        text = self.message or self.story or "(no text — media or shared content)"
        text = " ".join(text.split())  # collapse whitespace/newlines
        if len(text) > 80:
            text = text[:77] + "..."
        return text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_time": self.created_time,
            "message": self.message,
            "story": self.story,
            "permalink_url": self.permalink_url,
            "comment_count": self.comment_count,
            "reaction_count": self.reaction_count,
        }


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

    def _request(self, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 token: Optional[str] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params["access_token"] = token or self._token
        url = path if path.startswith("http") else f"{BASE_URL}/{path.lstrip('/')}"
        try:
            resp = self._session.request(method, url, params=params, timeout=REQUEST_TIMEOUT)
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

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
             token: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", path, params, token)

    def _post(self, path: str, params: Optional[Dict[str, Any]] = None,
              token: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", path, params, token)

    def _iter_edge(self, path: str, params: Dict[str, Any],
                   *, max_pages: int = 20, token: Optional[str] = None
                   ) -> Iterator[Dict[str, Any]]:
        """Yield items from a paginated edge, following `paging.next`."""
        payload = self._get(path, params, token=token)
        pages = 0
        while True:
            for item in payload.get("data", []):
                yield item
            pages += 1
            next_url = payload.get("paging", {}).get("next")
            if not next_url or pages >= max_pages:
                break
            payload = self._get(next_url, token=token)

    # -- read-only operations on the token owner's own account ------------

    def me(self) -> Dict[str, Any]:
        """Return the token owner's basic public profile (id + name)."""
        return self._get("me", {"fields": "id,name"})

    def permissions(self) -> List[Dict[str, str]]:
        """Return the list of permissions granted to this token."""
        data = self._get("me/permissions")
        return list(data.get("data", []))

    def debug_token(self, app_token: Optional[str] = None) -> Dict[str, Any]:
        """Inspect the current access token (validity, scopes, expiry).

        /debug_token is best called with an app access token
        (`APP_ID|APP_SECRET`). If `app_token` isn't given we fall back to the
        user token itself, which Facebook accepts for some apps but may
        reject with "an app access_token is required" — in which case the
        caller should supply an app token.
        """
        data = self._get(
            "debug_token",
            {"input_token": self._token},
            token=app_token or self._token,
        )
        return data.get("data", {})

    def friend_summary(self) -> Dict[str, Any]:
        """Return the friend-count summary for the token owner.

        The Graph API only exposes a *count* here, and only counts friends
        who also use the same app. There is no official way to list, add, or
        remove friends.
        """
        data = self._get("me/friends", {"summary": "true", "limit": 0})
        summary = data.get("summary", {})
        return {
            "total_count": summary.get("total_count"),
            "app_friends_returned": len(data.get("data", [])),
        }

    def iter_posts(self, *, page_limit: int = 25, max_pages: int = 20,
                   include_engagement: bool = False) -> Iterator[Post]:
        """Yield the token owner's own posts, newest first (read-only).

        Requires the `user_posts` permission. With `include_engagement`, the
        aggregate comment and reaction counts on each post are also fetched
        (counts only, never who commented or reacted).
        """
        fields = ["id", "created_time", "message", "story", "permalink_url"]
        if include_engagement:
            fields.append("comments.summary(true).limit(0)")
            fields.append("reactions.summary(true).limit(0)")
        params = {"fields": ",".join(fields), "limit": page_limit}
        for item in self._iter_edge("me/posts", params, max_pages=max_pages):
            yield Post(
                id=item.get("id", ""),
                created_time=item.get("created_time"),
                message=item.get("message"),
                story=item.get("story"),
                permalink_url=item.get("permalink_url"),
                comment_count=item.get("comments", {}).get("summary", {}).get("total_count"),
                reaction_count=item.get("reactions", {}).get("summary", {}).get("total_count"),
            )

    def iter_uploaded_photos(self, *, max_pages: int = 20) -> Iterator[Dict[str, Any]]:
        """Yield metadata for photos the user uploaded (needs `user_photos`)."""
        params = {
            "type": "uploaded",
            "fields": "id,created_time,name,link,album{name}",
            "limit": 25,
        }
        yield from self._iter_edge("me/photos", params, max_pages=max_pages)

    def iter_uploaded_videos(self, *, max_pages: int = 20) -> Iterator[Dict[str, Any]]:
        """Yield metadata for videos the user uploaded (needs `user_videos`)."""
        params = {
            "type": "uploaded",
            "fields": "id,created_time,title,description,permalink_url",
            "limit": 25,
        }
        yield from self._iter_edge("me/videos", params, max_pages=max_pages)

    # -- Pages the user administers --------------------------------------

    def list_pages(self) -> List[Dict[str, Any]]:
        """List Pages the user manages, with a page access token for each.

        Needs `pages_show_list`. Each entry includes the Page's own access
        token, which is what Page write/insight calls must use.
        """
        data = self._get(
            "me/accounts",
            {"fields": "id,name,category,access_token,tasks", "limit": 50},
        )
        return list(data.get("data", []))

    def page_publish(self, page_id: str, page_token: str, message: str,
                     link: Optional[str] = None) -> Dict[str, Any]:
        """Publish a text (optionally link) post to a Page you manage.

        Needs `pages_manage_posts`. This posts to a *Page*, which the official
        API supports — unlike posting to a personal timeline, which it does
        not allow for third-party apps.
        """
        params: Dict[str, Any] = {"message": message}
        if link:
            params["link"] = link
        return self._post(f"{page_id}/feed", params, token=page_token)

    def page_insights(self, page_id: str, page_token: str,
                      metrics: List[str], period: str = "day") -> List[Dict[str, Any]]:
        """Read insights for a Page you manage (needs `read_insights`)."""
        data = self._get(
            f"{page_id}/insights",
            {"metric": ",".join(metrics), "period": period},
            token=page_token,
        )
        return list(data.get("data", []))

    def page_reply_to_comment(self, comment_id: str, page_token: str,
                              message: str) -> Dict[str, Any]:
        """Reply to a comment on your Page's post (needs `pages_manage_engagement`)."""
        return self._post(f"{comment_id}/comments", {"message": message}, token=page_token)
