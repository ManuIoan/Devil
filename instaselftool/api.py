"""A thin wrapper around the official Instagram Graph API.

Everything here is scoped to the Instagram Professional account that the
supplied access token controls. The Instagram Graph API runs on
graph.facebook.com and requires an Instagram Business/Creator account linked
to a Facebook Page; the token is a Facebook user/Page token carrying the
relevant `instagram_*` permissions.

Only operations the official API genuinely supports are implemented, and none
of them read, store, or act on anyone else's account (replying to a comment on
your own media is the one place another person's public comment is involved,
and only because you chose to answer it).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import requests

GRAPH_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
REQUEST_TIMEOUT = 60  # publishing / media fetches can be slower than reads


class InstagramAPIError(RuntimeError):
    """Raised when the Instagram Graph API returns an error or HTTP failure."""

    def __init__(self, message: str, *, code: Optional[int] = None,
                 type_: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.type = type_
        self.http_status = http_status


@dataclass
class IGAccount:
    """An Instagram Professional account reachable through a linked Page."""

    ig_id: str
    username: Optional[str]
    page_id: str
    page_name: Optional[str]
    page_token: str


@dataclass
class Media:
    """One media object on the user's own Instagram account."""

    id: str
    media_type: Optional[str] = None
    caption: Optional[str] = None
    permalink: Optional[str] = None
    media_url: Optional[str] = None
    timestamp: Optional[str] = None
    like_count: Optional[int] = None
    comments_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "media_type": self.media_type,
            "caption": self.caption,
            "permalink": self.permalink,
            "media_url": self.media_url,
            "timestamp": self.timestamp,
            "like_count": self.like_count,
            "comments_count": self.comments_count,
        }


class InstagramClient:
    """Minimal Instagram Graph API client scoped to the token owner's account.

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
            raise InstagramAPIError(f"Network error talking to the Instagram API: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError:
            raise InstagramAPIError(
                f"Instagram API returned a non-JSON response (HTTP {resp.status_code}).",
                http_status=resp.status_code,
            )

        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            raise InstagramAPIError(
                err.get("message", "Unknown Instagram API error."),
                code=err.get("code"),
                type_=err.get("type"),
                http_status=resp.status_code,
            )
        if not resp.ok:
            raise InstagramAPIError(
                f"Instagram API request failed with HTTP {resp.status_code}.",
                http_status=resp.status_code,
            )
        return payload

    def _get(self, path, params=None, token=None):
        return self._request("GET", path, params, token)

    def _post(self, path, params=None, token=None):
        return self._request("POST", path, params, token)

    def _iter_edge(self, path, params, *, max_pages=20, token=None) -> Iterator[Dict[str, Any]]:
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

    # -- account discovery ------------------------------------------------

    def discover_accounts(self) -> List[IGAccount]:
        """Find Instagram Professional accounts linked to the user's Pages.

        Needs `pages_show_list` plus `instagram_basic`. The Instagram Graph API
        reaches an IG account through the Facebook Page it is linked to, so we
        list the Pages and read each one's `instagram_business_account`.
        """
        data = self._get(
            "me/accounts",
            {"fields": "id,name,access_token,instagram_business_account{id,username}", "limit": 50},
        )
        accounts: List[IGAccount] = []
        for page in data.get("data", []):
            ig = page.get("instagram_business_account")
            if not ig:
                continue
            accounts.append(IGAccount(
                ig_id=ig.get("id"),
                username=ig.get("username"),
                page_id=page.get("id"),
                page_name=page.get("name"),
                page_token=page.get("access_token") or self._token,
            ))
        return accounts

    # -- read-only operations on the user's own account ------------------

    def profile(self, account: IGAccount) -> Dict[str, Any]:
        """Return the account's own profile fields (needs `instagram_basic`)."""
        fields = ("username,name,biography,website,followers_count,"
                  "follows_count,media_count,profile_picture_url")
        return self._get(account.ig_id, {"fields": fields}, token=account.page_token)

    def iter_media(self, account: IGAccount, *, max_pages: int = 20) -> Iterator[Media]:
        """Yield the account's own media, newest first (needs `instagram_basic`)."""
        fields = ("id,caption,media_type,media_url,permalink,timestamp,"
                  "like_count,comments_count")
        params = {"fields": fields, "limit": 25}
        for item in self._iter_edge(f"{account.ig_id}/media", params,
                                    max_pages=max_pages, token=account.page_token):
            yield Media(
                id=item.get("id", ""),
                media_type=item.get("media_type"),
                caption=item.get("caption"),
                permalink=item.get("permalink"),
                media_url=item.get("media_url"),
                timestamp=item.get("timestamp"),
                like_count=item.get("like_count"),
                comments_count=item.get("comments_count"),
            )

    def account_insights(self, account: IGAccount, metrics: List[str],
                         period: str = "day") -> List[Dict[str, Any]]:
        """Read account-level insights (needs `instagram_manage_insights`)."""
        data = self._get(
            f"{account.ig_id}/insights",
            {"metric": ",".join(metrics), "period": period},
            token=account.page_token,
        )
        return list(data.get("data", []))

    def media_insights(self, account: IGAccount, media_id: str,
                       metrics: List[str]) -> List[Dict[str, Any]]:
        """Read insights for one of the account's own media items."""
        data = self._get(
            f"{media_id}/insights",
            {"metric": ",".join(metrics)},
            token=account.page_token,
        )
        return list(data.get("data", []))

    def iter_comments(self, account: IGAccount, media_id: str,
                      *, max_pages: int = 10) -> Iterator[Dict[str, Any]]:
        """Yield comments on one of the account's own media items.

        Needs `instagram_manage_comments`. Used so the owner can read and
        answer comments on their own posts.
        """
        params = {"fields": "id,text,timestamp,username", "limit": 25}
        yield from self._iter_edge(f"{media_id}/comments", params,
                                   max_pages=max_pages, token=account.page_token)

    def reply_to_comment(self, account: IGAccount, comment_id: str,
                         message: str) -> Dict[str, Any]:
        """Reply to a comment on the account's own media (`instagram_manage_comments`)."""
        return self._post(f"{comment_id}/replies", {"message": message},
                          token=account.page_token)

    # -- content publishing (the user's own account) --------------------

    def _create_container(self, account: IGAccount, params: Dict[str, Any]) -> str:
        result = self._post(f"{account.ig_id}/media", params, token=account.page_token)
        creation_id = result.get("id")
        if not creation_id:
            raise InstagramAPIError("Media container creation returned no id.")
        return creation_id

    def _publish_container(self, account: IGAccount, creation_id: str) -> Dict[str, Any]:
        return self._post(f"{account.ig_id}/media_publish",
                         {"creation_id": creation_id}, token=account.page_token)

    def publish_image(self, account: IGAccount, image_url: str,
                      caption: Optional[str] = None) -> Dict[str, Any]:
        """Publish a photo to the account (needs `instagram_content_publish`).

        `image_url` must be a publicly reachable URL — Instagram fetches the
        image itself; there is no direct file upload for photos.
        """
        params: Dict[str, Any] = {"image_url": image_url}
        if caption:
            params["caption"] = caption
        creation_id = self._create_container(account, params)
        return self._publish_container(account, creation_id)

    def publish_reel(self, account: IGAccount, video_url: str,
                     caption: Optional[str] = None, *,
                     poll_interval: float = 5.0, max_polls: int = 12) -> Dict[str, Any]:
        """Publish a video as a Reel (needs `instagram_content_publish`).

        `video_url` must be publicly reachable. Video containers are processed
        asynchronously, so we poll the container's `status_code` until it is
        FINISHED (or raise if it errors / times out) before publishing.
        """
        params: Dict[str, Any] = {"media_type": "REELS", "video_url": video_url}
        if caption:
            params["caption"] = caption
        creation_id = self._create_container(account, params)

        for _ in range(max_polls):
            status = self._get(creation_id, {"fields": "status_code"},
                               token=account.page_token)
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise InstagramAPIError("Instagram reported an error processing the video.")
            if poll_interval:
                time.sleep(poll_interval)
        else:
            raise InstagramAPIError(
                "Video was still processing after the wait; try publishing again shortly."
            )
        return self._publish_container(account, creation_id)
