"""Interactive command-line menu for fbselftool.

The token is read from the FB_ACCESS_TOKEN environment variable if present,
otherwise it is prompted for (hidden input). It is kept only in memory.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from getpass import getpass
from typing import Optional

from .api import GraphAPIClient, GraphAPIError

TOKEN_ENV_VAR = "FB_ACCESS_TOKEN"
APP_TOKEN_ENV_VAR = "FB_APP_TOKEN"  # optional: "APP_ID|APP_SECRET" for /debug_token

BANNER = """\
============================================================
  fbselftool — legal self-account helper (official Graph API)
  Acts only on YOUR account / Pages, using a token YOU supply.
============================================================"""

MENU = """\
  [1] Show my profile (id + name)
  [2] Show which permissions my token has
  [3] List my own posts (read-only)
  [4] Show my friend count
  [5] Export a full backup to JSON (profile, posts, photos, videos)
  [6] Token info — validity, scopes, expiry
  [7] Pages I manage (post / insights / reply to comments)
  [8] What's NOT possible, and why
  [0] Exit"""


def _load_token() -> Optional[str]:
    """Get the access token from the environment or an interactive prompt."""
    token = os.environ.get(TOKEN_ENV_VAR)
    if token and token.strip():
        print(f"[+] Using access token from ${TOKEN_ENV_VAR}.")
        return token.strip()
    print(
        "\nPaste a Facebook *user* access token for your own account.\n"
        "It is kept in memory only — never written to disk.\n"
        "See the README for how to generate one with the right permissions.\n"
    )
    try:
        token = getpass("Access token (input hidden): ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return token.strip() or None


def _prompt(label: str) -> Optional[str]:
    """Prompt for a line of input, returning None on Ctrl-C/EOF."""
    try:
        return input(label).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _fmt_ts(value) -> str:
    """Render a unix timestamp (or 0 = never) as a readable string."""
    if not value:
        return "never (long-lived or no expiry)"
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return str(value)


# -- individual actions ---------------------------------------------------

def _action_profile(client: GraphAPIClient) -> None:
    me = client.me()
    print(f"\n  Name : {me.get('name', '(unknown)')}")
    print(f"  ID   : {me.get('id', '(unknown)')}")


def _action_permissions(client: GraphAPIClient) -> None:
    perms = client.permissions()
    if not perms:
        print("\n  No permissions reported for this token.")
        return
    print("\n  Permissions on this token:")
    for entry in perms:
        name = entry.get("permission", "?")
        status = entry.get("status", "?")
        mark = "✓" if status == "granted" else "✗"
        print(f"    [{mark}] {name} ({status})")


def _action_posts(client: GraphAPIClient) -> None:
    print("\n  Fetching your posts (needs the 'user_posts' permission)...\n")
    count = 0
    for post in client.iter_posts():
        count += 1
        when = post.created_time or "(no date)"
        print(f"  {count:>3}. {when}")
        print(f"       {post.summary}")
        if post.permalink_url:
            print(f"       {post.permalink_url}")
    if count == 0:
        print("  No posts returned. Either you have none, or your token is")
        print("  missing the 'user_posts' permission.")
    else:
        print(f"\n  Listed {count} post(s). This view is read-only.")


def _action_friend_count(client: GraphAPIClient) -> None:
    info = client.friend_summary()
    total = info.get("total_count")
    print(f"\n  Total friends: {total if total is not None else '(not available)'}")
    print("  Note: the official API only exposes a count — it cannot list,")
    print("  add, or remove friends. See option [8] for details.")


def _collect(label: str, iterator) -> list:
    """Drain an iterator into a list, reporting permission errors softly."""
    try:
        return list(iterator)
    except GraphAPIError as exc:
        print(f"    - {label}: skipped ({exc})")
        return []


def _action_export_backup(client: GraphAPIClient) -> None:
    default_name = f"fb_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
    raw = _prompt(f"\n  Save backup to [{default_name}]: ")
    if raw is None:
        print("  Export cancelled.")
        return
    path = raw or default_name

    print("\n  Collecting your account data (only what the API allows)...")
    backup: dict = {"exported_at": datetime.now().astimezone().isoformat()}

    try:
        backup["profile"] = client.me()
    except GraphAPIError as exc:
        print(f"    - profile: skipped ({exc})")
    try:
        backup["friends"] = client.friend_summary()
    except GraphAPIError as exc:
        print(f"    - friend count: skipped ({exc})")

    posts = _collect("posts", client.iter_posts(include_engagement=True))
    backup["posts"] = [p.to_dict() for p in posts]
    backup["photos"] = _collect("photos", client.iter_uploaded_photos())
    backup["videos"] = _collect("videos", client.iter_uploaded_videos())

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(backup, fh, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"\n  [!] Could not write '{path}': {exc}")
        return
    print(
        f"\n  Saved backup to {os.path.abspath(path)}\n"
        f"    posts: {len(backup['posts'])}  "
        f"photos: {len(backup['photos'])}  "
        f"videos: {len(backup['videos'])}"
    )


def _action_token_info(client: GraphAPIClient) -> None:
    app_token = os.environ.get(APP_TOKEN_ENV_VAR)
    try:
        data = client.debug_token(app_token=app_token)
    except GraphAPIError as exc:
        print(f"\n  [!] Could not inspect the token: {exc}")
        if not app_token:
            print(f"      Tip: set ${APP_TOKEN_ENV_VAR}='APP_ID|APP_SECRET' and retry —")
            print("      /debug_token is meant to be called with an app access token.")
        return
    print("\n  Token details:")
    print(f"    Valid           : {data.get('is_valid')}")
    print(f"    App ID          : {data.get('app_id')}")
    print(f"    Type            : {data.get('type')}")
    print(f"    Expires at      : {_fmt_ts(data.get('expires_at'))}")
    print(f"    Data access ends: {_fmt_ts(data.get('data_access_expires_at'))}")
    scopes = data.get("scopes") or []
    if scopes:
        print(f"    Scopes          : {', '.join(scopes)}")
    print(
        "\n  To refresh: Graph API Explorer tokens are short-lived (~1 hour).\n"
        "  For a long-lived user token (~60 days), exchange a short-lived one\n"
        "  server-side with your app secret:\n"
        "    GET /oauth/access_token?grant_type=fb_exchange_token\n"
        "        &client_id=APP_ID&client_secret=APP_SECRET\n"
        "        &fb_exchange_token=SHORT_LIVED_TOKEN\n"
        "  (Keep the app secret off this machine / out of version control.)"
    )


# -- Pages submenu --------------------------------------------------------

PAGES_MENU = """\
    [1] Post to a Page you manage
    [2] Read a Page's insights
    [3] Reply to a comment on a Page post
    [0] Back"""


def _choose_page(client: GraphAPIClient) -> Optional[dict]:
    pages = client.list_pages()
    if not pages:
        print("\n  No Pages found for this account. (Needs 'pages_show_list',")
        print("  and you must be an admin/editor of at least one Page.)")
        return None
    print("\n  Pages you manage:")
    for i, page in enumerate(pages, 1):
        print(f"    [{i}] {page.get('name')} (id {page.get('id')})")
    raw = _prompt("  Choose a Page > ")
    if not raw:
        return None
    if not raw.isdigit() or not (1 <= int(raw) <= len(pages)):
        print("  [!] Invalid choice.")
        return None
    return pages[int(raw) - 1]


def _page_post(client: GraphAPIClient) -> None:
    page = _choose_page(client)
    if not page:
        return
    if not page.get("access_token"):
        print("  [!] No page access token available (missing 'pages_manage_posts'?).")
        return
    message = _prompt("  Post text > ")
    if not message:
        print("  Nothing to post.")
        return
    link = _prompt("  Optional link (blank for none) > ") or None
    confirm = _prompt(f"  Publish this to '{page.get('name')}'? [y/N] > ")
    if (confirm or "").lower() != "y":
        print("  Cancelled.")
        return
    result = client.page_publish(page["id"], page["access_token"], message, link)
    print(f"  Published. Post id: {result.get('id', '(unknown)')}")


def _page_insights(client: GraphAPIClient) -> None:
    page = _choose_page(client)
    if not page or not page.get("access_token"):
        return
    metrics = ["page_impressions", "page_post_engagements", "page_fans"]
    print(f"\n  Insights for '{page.get('name')}' ({', '.join(metrics)}):")
    rows = client.page_insights(page["id"], page["access_token"], metrics)
    if not rows:
        print("    (no insight data returned — needs 'read_insights')")
        return
    for row in rows:
        values = row.get("values", [])
        latest = values[-1].get("value") if values else "(n/a)"
        print(f"    {row.get('name')}: {latest}")


def _page_reply(client: GraphAPIClient) -> None:
    page = _choose_page(client)
    if not page or not page.get("access_token"):
        return
    comment_id = _prompt("  Comment id to reply to > ")
    if not comment_id:
        return
    message = _prompt("  Reply text > ")
    if not message:
        print("  Nothing to send.")
        return
    confirm = _prompt("  Post this reply? [y/N] > ")
    if (confirm or "").lower() != "y":
        print("  Cancelled.")
        return
    result = client.page_reply_to_comment(comment_id, page["access_token"], message)
    print(f"  Replied. Comment id: {result.get('id', '(unknown)')}")


def _action_pages(client: GraphAPIClient) -> None:
    handlers = {"1": _page_post, "2": _page_insights, "3": _page_reply}
    while True:
        print("\n" + PAGES_MENU)
        choice = _prompt("  Choose an option > ")
        if choice is None or choice == "0":
            return
        handler = handlers.get(choice)
        if handler is None:
            print("  [!] Unknown option.")
            continue
        try:
            handler(client)
        except GraphAPIError as exc:
            print(f"  [!] Graph API error: {exc}")


def _action_explain() -> None:
    print(
        """
  What this tool does NOT do, and why:

    • Unfriend / list friends — /me/friends is read-only ("You can't delete
      using this edge") and the full list was removed after Graph API v3.2.
    • Accept friend requests  — there is no official edge to read or accept a
      person's incoming friend requests.
    • Delete your own posts   — removed with the 'publish_actions' permission
      in 2018. 'user_posts' is read-only.
    • Post to your personal   — also removed with 'publish_actions' in 2018.
      timeline / upload a        Third-party apps can no longer publish to a
      personal photo             personal profile. (Posting to a PAGE you
                                 manage IS supported — see option [7].)
    • Anything about other    — this tool never reads, stores, or acts on
      people's accounts          anyone else's account or personal data.

  The original project did some of these by impersonating the Facebook
  Android app with a spoofed user-agent and a hard-coded app token. That
  breaks Facebook's Platform Terms, so this rebuild does not do it. To delete
  posts, manage friends, or post to your personal timeline, use the Facebook
  website or app directly.
"""
    )


# -- main loop ------------------------------------------------------------

def run() -> int:
    print(BANNER)
    token = _load_token()
    if not token:
        print("\n[!] No access token provided. Exiting.")
        return 1

    try:
        client = GraphAPIClient(token)
    except ValueError as exc:
        print(f"\n[!] {exc}")
        return 1

    # Verify the token up front so we fail fast on a bad/expired one.
    try:
        me = client.me()
        print(f"\n[+] Authenticated as: {me.get('name')} (id {me.get('id')})")
    except GraphAPIError as exc:
        print(f"\n[!] Could not authenticate with that token: {exc}")
        return 1

    handlers = {
        "1": lambda: _action_profile(client),
        "2": lambda: _action_permissions(client),
        "3": lambda: _action_posts(client),
        "4": lambda: _action_friend_count(client),
        "5": lambda: _action_export_backup(client),
        "6": lambda: _action_token_info(client),
        "7": lambda: _action_pages(client),
        "8": _action_explain,
    }

    while True:
        print("\n" + MENU)
        choice = _prompt("\n  Choose an option > ")
        if choice is None or choice == "0":
            print("[+] Bye.")
            return 0
        handler = handlers.get(choice)
        if handler is None:
            print("[!] Unknown option.")
            continue
        try:
            handler()
        except GraphAPIError as exc:
            print(f"\n[!] Graph API error: {exc}")
            if exc.code:
                print(f"    (code {exc.code}, type {exc.type})")
