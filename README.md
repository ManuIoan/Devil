# fbselftool & instaselftool

Small, **legal** command-line helpers for your **own** Facebook and Instagram
accounts, built on the **official Graph APIs**.

- **`fbselftool`** — your own Facebook account (and Pages you administer).
- **`instaselftool`** — your own Instagram Professional account (see the
  [Instagram section](#instagram-instaselftool) below).

This is a clean Python 3 rebuild of an old Python 2 project. The original was
a "Facebook hacking" tool; this rebuild keeps only the features that act on
*your own account* through the official API, and drops everything abusive.
It never impersonates the Facebook/Instagram apps, never scrapes, and never
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

---

## Instagram (`instaselftool`)

A companion tool for your **own Instagram Professional account**, built on the
official **Instagram Graph API** (which also runs on `graph.facebook.com`).
Same rules as the Facebook side: only your own account, official API only, no
scraping, no app impersonation.

### Requirement

The Instagram Graph API only works with an Instagram **Professional** account
(Business or Creator) that is **linked to a Facebook Page**. A personal
Instagram account cannot be used. The tool finds your Instagram account through
that linked Page (`/me/accounts` → `instagram_business_account`).

### What it does

| Option | What it does | Permission needed |
| ------ | ------------ | ----------------- |
| Show my profile | Username, name, bio, website, follower/following/media counts | `instagram_basic` |
| Export my media | Save your media (id, caption, type, permalink, timestamp, like/comment counts) to a JSON backup | `instagram_basic` |
| Account insights | Reach, follower count, etc. for your account | `instagram_manage_insights` |
| Media insights | Reach, likes, comments, saves for one media item | `instagram_manage_insights` |
| Comments + reply | Read comments on one of your media and reply to one (asks to confirm) | `instagram_manage_comments` |
| Publish a photo | Publish a photo by **public image URL** (asks to confirm) | `instagram_content_publish` |
| Publish a reel | Publish a video/reel by **public video URL** (waits for processing, asks to confirm) | `instagram_content_publish` |

Finding the linked account also needs `pages_show_list`. All of these
`instagram_*` permissions require Facebook **App Review / Advanced Access** to
work beyond your own test users.

> **Publishing note:** Instagram's official content-publishing endpoint fetches
> media from a **publicly reachable URL** you provide — there is no direct
> upload of a local file for photos, and videos are processed asynchronously
> (the tool polls until processing finishes before publishing).

### Usage

```bash
export IG_ACCESS_TOKEN="your-user-or-page-token"   # falls back to FB_ACCESS_TOKEN
python -m instaselftool
```

...or run it and paste the token when prompted. Same token rules: in memory
only, never written to disk.

### Not possible through the official API (so it isn't offered)

- Acting on a **personal** (non-Professional) Instagram account.
- Reading or acting on **anyone else's** account, followers, or DMs by
  scraping.
- Auto-follow / unfollow, bulk actions, or any growth-automation — not exposed
  by the official API for that purpose and against the Platform Terms.

---

## Project layout

```
fbselftool/        Facebook self-account tool
  __init__.py      package metadata
  __main__.py      `python -m fbselftool` entry point
  api.py           official Graph API client (own account + your Pages)
  cli.py           interactive menu

instaselftool/     Instagram self-account tool
  __init__.py      package metadata
  __main__.py      `python -m instaselftool` entry point
  api.py           official Instagram Graph API client (your own IG account)
  cli.py           interactive menu
```

## Legal

Use these only on your own accounts, with your own token. You are responsible
for complying with Facebook's and Instagram's
[Platform Terms](https://developers.facebook.com/terms/) and all applicable
laws. These tools are provided as-is, with no warranty.
