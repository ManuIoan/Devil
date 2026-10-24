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

All actions below are **read-only** and run against the official Graph API
(`graph.facebook.com`, pinned to `v21.0`):

| Option | What it shows |
| ------ | ------------- |
| Show my profile | Your own `id` and `name` (`public_profile`) |
| Show my token's permissions | Which scopes your token was granted |
| List my own posts | Your own posts, newest first (`user_posts`) |
| Show my friend count | Your total friend count only (see caveat below) |
| Explain write actions | Why deleting posts / accepting requests / unfriending isn't possible |

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

The three "self-account" write actions from the original tool are **not
available** through the official Graph API for a normal third-party app on a
personal account, so this rebuild does **not** implement them:

- **Unfriend** — the `/me/friends` edge is documented as read-only ("You
  can't delete using this edge") and was removed after Graph API v3.2.
- **Accept friend requests** — there is no official edge to read or accept a
  person's incoming friend requests.
- **Delete your own posts** — publishing to and deleting from a personal
  timeline was removed together with the `publish_actions` permission in 2018.
  `user_posts` grants read-only access only.

Even the friend count is limited: the Graph API only returns a *number*, and
only counts friends who also use the same app — it cannot list, add, or remove
friends.

To actually delete posts, manage friend requests, or unfriend, use the
Facebook website or app directly. (Post management *is* available via the API
for **Pages you administer**, which is a different thing from your personal
timeline and out of scope for this tool.)

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
   - `user_posts` — list your own posts
   - `user_friends` — your friend count
5. Copy the generated **User Token**.

Tokens from the Explorer are short-lived (about an hour), which is fine for a
quick session. See Facebook's docs on
[access tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/)
for longer-lived tokens.

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
