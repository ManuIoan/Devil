"""Interactive command-line menu for instaselftool.

The token is read from IG_ACCESS_TOKEN (falling back to FB_ACCESS_TOKEN) if
present, otherwise it is prompted for (hidden input). It is kept only in
memory. The token must be a Facebook user/Page token with the relevant
instagram_* permissions, and your Instagram account must be a Professional
(Business/Creator) account linked to a Facebook Page.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from getpass import getpass
from typing import List, Optional

from .api import IGAccount, InstagramAPIError, InstagramClient

TOKEN_ENV_VARS = ("IG_ACCESS_TOKEN", "FB_ACCESS_TOKEN")

BANNER = """\
============================================================
  instaselftool — legal self-account helper (Instagram API)
  Acts only on YOUR Instagram Professional account.
============================================================"""

MENU = """\
  [1] Show my Instagram profile
  [2] Export my media to a JSON backup
  [3] Account insights
  [4] Insights for one media item
  [5] Read & reply to comments on one of my media
  [6] Publish a photo (by public image URL)
  [7] Publish a reel/video (by public video URL)
  [8] Requirements & what's not possible
  [0] Exit"""


def _load_token() -> Optional[str]:
    for var in TOKEN_ENV_VARS:
        token = os.environ.get(var)
        if token and token.strip():
            print(f"[+] Using access token from ${var}.")
            return token.strip()
    print(
        "\nPaste a Facebook user/Page access token that carries your\n"
        "instagram_* permissions. It is kept in memory only — never written\n"
        "to disk. See the README for how to generate one.\n"
    )
    try:
        token = getpass("Access token (input hidden): ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return token.strip() or None


def _prompt(label: str) -> Optional[str]:
    try:
        return input(label).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _confirm(label: str) -> bool:
    answer = _prompt(label)
    return (answer or "").lower() == "y"


# -- actions --------------------------------------------------------------

def _action_profile(client: InstagramClient, account: IGAccount) -> None:
    p = client.profile(account)
    print(f"\n  Username  : @{p.get('username', '(unknown)')}")
    print(f"  Name      : {p.get('name', '')}")
    print(f"  Bio       : {p.get('biography', '')}")
    if p.get("website"):
        print(f"  Website   : {p.get('website')}")
    print(f"  Followers : {p.get('followers_count', '(n/a)')}")
    print(f"  Following : {p.get('follows_count', '(n/a)')}")
    print(f"  Media     : {p.get('media_count', '(n/a)')}")


def _action_export(client: InstagramClient, account: IGAccount) -> None:
    default_name = f"ig_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
    raw = _prompt(f"\n  Save backup to [{default_name}]: ")
    if raw is None:
        print("  Export cancelled.")
        return
    path = raw or default_name

    print("\n  Collecting your media (needs 'instagram_basic')...")
    media = [m.to_dict() for m in client.iter_media(account)]
    backup = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "account": {"ig_id": account.ig_id, "username": account.username},
        "media_count": len(media),
        "media": media,
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(backup, fh, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"\n  [!] Could not write '{path}': {exc}")
        return
    print(f"\n  Saved {len(media)} media item(s) to {os.path.abspath(path)}")


def _action_account_insights(client: InstagramClient, account: IGAccount) -> None:
    metrics = ["reach", "follower_count"]
    print(f"\n  Account insights ({', '.join(metrics)}, needs 'instagram_manage_insights'):")
    rows = client.account_insights(account, metrics)
    if not rows:
        print("    (no data returned)")
        return
    for row in rows:
        values = row.get("values", [])
        latest = values[-1].get("value") if values else "(n/a)"
        print(f"    {row.get('name')}: {latest}")


def _action_media_insights(client: InstagramClient, account: IGAccount) -> None:
    media_id = _prompt("\n  Media id > ")
    if not media_id:
        return
    metrics = ["reach", "likes", "comments", "saved"]
    rows = client.media_insights(account, media_id, metrics)
    if not rows:
        print("    (no data returned)")
        return
    print(f"\n  Insights for media {media_id}:")
    for row in rows:
        values = row.get("values", [])
        latest = values[-1].get("value") if values else "(n/a)"
        print(f"    {row.get('name')}: {latest}")


def _action_comments(client: InstagramClient, account: IGAccount) -> None:
    media_id = _prompt("\n  Media id to read comments on > ")
    if not media_id:
        return
    comments = list(client.iter_comments(account, media_id))
    if not comments:
        print("  No comments on that media (or missing 'instagram_manage_comments').")
        return
    print(f"\n  {len(comments)} comment(s):")
    for i, c in enumerate(comments, 1):
        print(f"    [{i}] @{c.get('username', '?')}: {c.get('text', '')}")
    raw = _prompt("\n  Reply to which number? (blank to skip) > ")
    if not raw or not raw.isdigit() or not (1 <= int(raw) <= len(comments)):
        return
    target = comments[int(raw) - 1]
    message = _prompt("  Reply text > ")
    if not message:
        print("  Nothing to send.")
        return
    if not _confirm(f"  Post this reply to @{target.get('username', '?')}? [y/N] > "):
        print("  Cancelled.")
        return
    result = client.reply_to_comment(account, target["id"], message)
    print(f"  Replied. Comment id: {result.get('id', '(unknown)')}")


def _action_publish_photo(client: InstagramClient, account: IGAccount) -> None:
    image_url = _prompt("\n  Public image URL > ")
    if not image_url:
        return
    caption = _prompt("  Caption (blank for none) > ") or None
    print("  Note: the URL must be publicly reachable — Instagram fetches it.")
    if not _confirm(f"  Publish this photo to @{account.username}? [y/N] > "):
        print("  Cancelled.")
        return
    result = client.publish_image(account, image_url, caption)
    print(f"  Published. Media id: {result.get('id', '(unknown)')}")


def _action_publish_reel(client: InstagramClient, account: IGAccount) -> None:
    video_url = _prompt("\n  Public video URL > ")
    if not video_url:
        return
    caption = _prompt("  Caption (blank for none) > ") or None
    print("  Note: the URL must be publicly reachable. Video processing may")
    print("  take a little while; the tool waits for it before publishing.")
    if not _confirm(f"  Publish this reel to @{account.username}? [y/N] > "):
        print("  Cancelled.")
        return
    result = client.publish_reel(account, video_url, caption)
    print(f"  Published. Media id: {result.get('id', '(unknown)')}")


def _action_explain() -> None:
    print(
        """
  Requirements
    • Your Instagram account must be a Professional account (Business or
      Creator) linked to a Facebook Page.
    • Your access token must carry the matching permissions, each of which
      needs Facebook App Review / Advanced Access to work beyond your own
      test users:
        - instagram_basic              profile + media (read)
        - instagram_manage_insights    account & media insights
        - instagram_manage_comments    read & reply to comments
        - instagram_content_publish    publish photos / reels
        - pages_show_list              find the linked account

  Not possible through the official API (so this tool does not do it)
    • Acting on a personal (non-Professional) Instagram account — the Graph
      API only supports Professional accounts.
    • Reading or acting on anyone else's account, followers, or DMs via
      scraping. This tool never does that.
    • Deleting comments from other people in bulk, auto-following/unfollowing,
      or any growth-automation — not offered by the official API for this
      purpose, and against the Platform Terms.
"""
    )


# -- account selection + main loop ---------------------------------------

def _choose_account(accounts: List[IGAccount]) -> Optional[IGAccount]:
    if len(accounts) == 1:
        return accounts[0]
    print("\n  Instagram accounts linked to your Pages:")
    for i, acc in enumerate(accounts, 1):
        print(f"    [{i}] @{acc.username} (via Page '{acc.page_name}')")
    raw = _prompt("  Choose an account > ")
    if not raw or not raw.isdigit() or not (1 <= int(raw) <= len(accounts)):
        return None
    return accounts[int(raw) - 1]


def run() -> int:
    print(BANNER)
    token = _load_token()
    if not token:
        print("\n[!] No access token provided. Exiting.")
        return 1

    try:
        client = InstagramClient(token)
    except ValueError as exc:
        print(f"\n[!] {exc}")
        return 1

    try:
        accounts = client.discover_accounts()
    except InstagramAPIError as exc:
        print(f"\n[!] Could not look up your Instagram account: {exc}")
        return 1

    if not accounts:
        print(
            "\n[!] No Instagram Professional account found.\n"
            "    Make sure your Instagram account is a Business/Creator account\n"
            "    linked to a Facebook Page, and that your token has\n"
            "    'pages_show_list' and 'instagram_basic'."
        )
        return 1

    account = _choose_account(accounts)
    if account is None:
        print("[!] No account selected. Exiting.")
        return 1
    print(f"\n[+] Using Instagram account: @{account.username} (id {account.ig_id})")

    handlers = {
        "1": _action_profile,
        "2": _action_export,
        "3": _action_account_insights,
        "4": _action_media_insights,
        "5": _action_comments,
        "6": _action_publish_photo,
        "7": _action_publish_reel,
    }

    while True:
        print("\n" + MENU)
        choice = _prompt("\n  Choose an option > ")
        if choice is None or choice == "0":
            print("[+] Bye.")
            return 0
        if choice == "8":
            _action_explain()
            continue
        handler = handlers.get(choice)
        if handler is None:
            print("[!] Unknown option.")
            continue
        try:
            handler(client, account)
        except InstagramAPIError as exc:
            print(f"\n[!] Instagram API error: {exc}")
            if exc.code:
                print(f"    (code {exc.code}, type {exc.type})")
