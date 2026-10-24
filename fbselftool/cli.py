"""Interactive command-line menu for fbselftool.

The token is read from the FB_ACCESS_TOKEN environment variable if present,
otherwise it is prompted for (hidden input). It is kept only in memory.
"""

from __future__ import annotations

import os
from getpass import getpass
from typing import Optional

from .api import GraphAPIClient, GraphAPIError

TOKEN_ENV_VAR = "FB_ACCESS_TOKEN"

BANNER = """\
============================================================
  fbselftool — legal self-account helper (official Graph API)
  Acts only on YOUR account, using a token YOU supply.
============================================================"""

MENU = """\
  [1] Show my profile (id + name)
  [2] Show which permissions my token has
  [3] List my own posts (read-only)
  [4] Show my friend count
  [5] What about delete posts / accept requests / unfriend?
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
    print("  add, or remove friends. See option [5] for details.")


def _action_explain_writes() -> None:
    print(
        """
  Why can't this tool delete posts, accept friend requests, or unfriend?

  Those actions are NOT available through Facebook's official Graph API
  for a normal third-party app acting on a personal account:

    • Unfriend         — the /me/friends edge is documented as read-only
                         ("You can't delete using this edge") and was
                         removed entirely after Graph API v3.2.
    • Friend requests  — there is no official edge to read or accept a
                         person's incoming friend requests.
    • Delete own posts — publishing/deleting personal timeline posts was
                         removed with the 'publish_actions' permission in
                         2018. 'user_posts' grants read-only access only.

  The original project did these by impersonating the Facebook Android app
  with a spoofed user-agent and a hard-coded app token. That is against
  Facebook's Platform Terms, so this rebuild does not do it. To manage your
  own posts, friends, or requests, use the Facebook website or app directly.
"""
    )


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

    while True:
        print("\n" + MENU)
        try:
            choice = input("\n  Choose an option > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[+] Bye.")
            return 0

        if choice == "0":
            print("[+] Bye.")
            return 0

        handlers = {
            "1": lambda: _action_profile(client),
            "2": lambda: _action_permissions(client),
            "3": lambda: _action_posts(client),
            "4": lambda: _action_friend_count(client),
            "5": _action_explain_writes,
        }
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
