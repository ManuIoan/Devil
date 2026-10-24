# fbselftool

A small, **legal** command-line helper for your **own** Facebook account,
built on Facebook's **official Graph API**.

This is a clean Python 3 rebuild of an old Python 2 project. The original was
a "Facebook hacking" tool; this rebuild keeps only the features that act on
*your own account* through the official API, and drops everything abusive.
It never impersonates the Facebook mobile app, never scrapes, and never
touches anyone else's data.

> **It only ever acts on the account that owns the access token you supply.**

---

## What it does

All actions run against the official Graph API (`graph.facebook.com`, pinned
to `v21.0`). Everything about your personal account is **read-only**; the only
write actions are on a Facebook **Page you administer** (and each one asks for
confirmation first):

| Option | What it does | Permission needed |
| ------ | ------------ | ----------------- |
| Show my profile | Your own `id` and `name` | `public_profile` |
| Show my token's permissions | Which scopes your token was granted | — |
| List my own posts | Your own posts, newest first (read-only) | `user_posts` |
| Show my friend count | Your total friend count only (see caveat) | `user_friends` |
| Export a full backup | Save profile, friend count, posts (+comment/reaction counts), and your uploaded photo/video metadata to a JSON file | `user_posts`, `user_photos`, `user_videos` |
| Token info | Validity, scopes, and expiry of your token, plus how to refresh | optional app token |
| Pages I manage | Post to, read insights for, and reply to comments on a Page you administer | `pages_show_list`, `pages_manage_posts`, `read_insights`, `pages_manage_engagement` |
| What's not possible | Why deleting posts / requests / unfriending / personal posting isn't available | — |

### Full backup

The backup writes a JSON file (default `fb_backup_<timestamp>.json`, or a name
you choose) with your profile, friend count, your posts (each with its
aggregate comment and reaction **counts** — never who commented or reacted),
and metadata for your uploaded photos and videos. Any section whose permission
your token is missing is skipped with a note, rather than failing the whole
export. It is a read-only backup of your own content and changes nothing on
Facebook.

### Pages you manage

If you administer a Facebook **Page**, the Pages menu can publish a post to it,
read basic insights, and reply to comments on its posts. These are the one set
of *write* actions the official API supports, because they act on a Page you
control (not on a personal timeline). Each action asks for confirmation before
it posts. The tool uses the per-Page access token that `/me/accounts` returns.

### Token info

Shows whether your token is valid, its scopes, and its expiry, and prints the
official `fb_exchange_token` flow for getting a long-lived token. Facebook's
`/debug_token` endpoint is designed to be called with an **app** access token,
so set `FB_APP_TOKEN="APP_ID|APP_SECRET"` for best results (it falls back to
the user token, which some apps reject).

## What was removed, and why

The original project has been **removed entirely** from this repository. None
of it was ported or referenced. Removed features:

- **Password brute-forcing / "account cloning" / login guessing** — this is
  account takeover. It is illegal and abusive. Dropped.
- **Harvesting other people's IDs, emails, and phone numbers from friend
  lists** — this is scraping other people's personal data. Dropped.
- **Impersonating the Facebook Android app** — the old code sent a spoofed
  `User-Agent` and a hard-coded app token to a private mobile endpoint. That
  violates Facebook's Platform Terms. This rebuild uses only the official,
  documented Graph API with a token you generate yourself.

The old tool also stored your token in a plaintext `login.txt` file and ran
`pip install` / `rm -rf` automatically. None of that happens here — the token
is held **in memory only**, and the tool installs and deletes nothing.

## What is *not* possible (and isn't faked)

Several write actions are **not available** through the official Graph API for
a normal third-party app on a *personal* account, so this rebuild does **not**
implement them (rather than faking them or impersonating the mobile app):

- **Unfriend** — the `/me/friends` edge is documented as read-only ("You
  can't delete using this edge") and was removed after Graph API v3.2.
- **Accept friend requests** — there is no official edge to read or accept a
  person's incoming friend requests.
- **Delete your own posts** — removed together with the `publish_actions`
  permission in 2018. `user_posts` grants read-only access only.
- **Post to your personal timeline / upload a personal photo** — also removed
  with `publish_actions` in 2018. Third-party apps can no longer publish to a
  personal profile. (Posting to a **Page** you manage *is* supported — see the
  Pages menu above.)

Even the friend count is limited: the Graph API only returns a *number*, and
only counts friends who also use the same app — it cannot list, add, or remove
friends.

To delete posts, manage friend requests, unfriend, or post to your personal
timeline, use the Facebook website or app directly.

---

## Requirements

- Python 3.11+
- [`requests`](https://pypi.org/project/requests/)

```bash
pip install -r requirements.txt
```

## Getting a user access token

1. Go to [developers.facebook.com](https://developers.facebook.com/) and
   create an app (type: *Consumer*) if you don't have one.
2. Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
3. Select your app, then **Generate Access Token**.
4. Add the permissions you want to use and grant them for **your own**
   account:
   - `public_profile` — profile (name + id)
   - `user_posts` — list / export your own posts
   - `user_friends` — your friend count
   - `user_photos`, `user_videos` — include uploaded photo/video metadata in
     the backup
   - `pages_show_list`, `pages_manage_posts`, `read_insights`,
     `pages_manage_engagement` — only if you want the Pages features
5. Copy the generated **User Token**.

> Several of these permissions (`user_posts`, `user_photos`, `user_videos`, the
> `pages_*` set) require Facebook **App Review / Advanced Access** before they
> work outside your own test users. Features whose permission you don't have
> simply report that and are skipped — nothing is faked.

Tokens from the Explorer are short-lived (about an hour), which is fine for a
quick session. The **Token info** menu option shows your token's expiry and
prints the official flow for exchanging it for a long-lived token. See
Facebook's docs on
[access tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/)
for details.

### Optional: app token for token inspection

`/debug_token` is meant to be called with an app access token. To use the
Token info option reliably, set:

```bash
export FB_APP_TOKEN="APP_ID|APP_SECRET"
```

Keep your app secret off shared machines and out of version control.

## Usage

Provide the token either via an environment variable:

```bash
export FB_ACCESS_TOKEN="your-user-token"
python -m fbselftool
```

...or just run it and paste the token when prompted (input is hidden):

```bash
python -m fbselftool
```

The token is never written to disk and never logged.

## Project layout

```
fbselftool/
  __init__.py     package metadata
  __main__.py     `python -m fbselftool` entry point
  api.py          official Graph API client (read-only, own account)
  cli.py          interactive menu
```

## Legal

Use this only on your own account, with your own token. You are responsible
for complying with Facebook's
[Platform Terms](https://developers.facebook.com/terms/) and all applicable
laws. This tool is provided as-is, with no warranty.
