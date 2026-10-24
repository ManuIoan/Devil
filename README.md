# fbselftool & instaselftool

Small, **legal** command-line helpers for your **own** Facebook and Instagram
accounts, built on the **official Graph APIs**. This is a clean Python 3
rebuild of an old Python 2 "Facebook hacking" project: it keeps only actions
that work on *your own* account through the official API and drops everything
abusive. It never impersonates the Facebook/Instagram apps, never scrapes, and
never touches anyone else's data.

Two tools live here:

- **`fbselftool`** — your own Facebook account (and Pages you administer).
- **`instaselftool`** — your own Instagram Professional account.

> **Scope (hard limits).** Your own account only. No password cracking, no
> harvesting other people's data, no unofficial/mobile-app endpoints. Some
> actions the original tool claimed simply aren't possible through the official
> API anymore — those are documented as such, not faked. See
> [What's not possible](#whats-not-possible).

---

## Quick start

```bash
# 1. Get the code and enter it
git clone https://github.com/ManuIoan/Devil.git
cd Devil

# 2. Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Provide a token (see "Getting a token" below) and run a tool
export FB_ACCESS_TOKEN="your-user-token"
python -m fbselftool                # Facebook
python -m instaselftool             # Instagram (same token works if it has IG scopes)
```

If you don't set the environment variable, each tool prompts for the token
(hidden input). The token is held **in memory only** — never written to disk,
never logged.

---

## Prerequisites

- **Python 3.11 or newer** (`python3 --version` to check).
- The **`requests`** library — installed by `pip install -r requirements.txt`.
- A Facebook **developer app** and an access token (next section).

A virtual environment (`venv`) is recommended but optional. Everything runs
locally; the only network calls are HTTPS requests to `graph.facebook.com`.

---

## Accounts you need

| Tool | Account requirement |
| ---- | ------------------- |
| `fbselftool` | A normal Facebook account. Page features also need a Facebook **Page** you administer. |
| `instaselftool` | An Instagram **Professional** account (Business or Creator) **linked to a Facebook Page**. A personal Instagram account will not work — the Instagram Graph API only supports Professional accounts, reached through the linked Page. |

---

## Getting a token

Both tools authenticate with a Facebook **user (or Page) access token** that
carries the permissions ("scopes") for the features you want to use.

1. Go to [developers.facebook.com](https://developers.facebook.com/) and create
   an app (type: *Consumer*) if you don't have one.
2. Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
3. Select your app, click **Generate Access Token**, and grant the permissions
   below for **your own** account.
4. Copy the generated token. Explorer tokens are short-lived (~1 hour), which
   is fine for a session; the Facebook tool's **Token info** option prints the
   official flow to exchange it for a long-lived (~60-day) token.

### Permissions (scopes)

Only add the scopes for the features you actually plan to use.

**Facebook (`fbselftool`):**

| Scope | Enables |
| ----- | ------- |
| `public_profile` | Your profile (name + id) |
| `user_posts` | List / export your own posts |
| `user_friends` | Your friend count |
| `user_photos`, `user_videos` | Photo/video metadata in the backup |
| `pages_show_list` | Find Pages you manage |
| `pages_manage_posts` | Publish a post to a Page you manage |
| `read_insights` | Read a Page's insights |
| `pages_manage_engagement` | Reply to comments on a Page's posts |

**Instagram (`instaselftool`):**

| Scope | Enables |
| ----- | ------- |
| `pages_show_list` | Find the Page your IG account is linked to |
| `instagram_basic` | Profile + media (read / export) |
| `instagram_manage_insights` | Account & media insights |
| `instagram_manage_comments` | Read & reply to comments on your media |
| `instagram_content_publish` | Publish a photo / reel |

> ⚠️ **App Review caveat.** Most of these (`user_posts`, `user_photos`,
> `user_videos`, the `pages_*` set, and all `instagram_*` scopes) require
> Facebook **App Review / Advanced Access** before they work for anyone other
> than the app's own admins/testers. Until then you can still use them against
> **your own** (developer/test) account. If your token is missing a scope, the
> affected feature just reports that and is skipped — nothing is faked.

---

## Environment variables

| Variable | Used by | Purpose |
| -------- | ------- | ------- |
| `FB_ACCESS_TOKEN` | both | Your Facebook user/Page token. `instaselftool` falls back to this if `IG_ACCESS_TOKEN` is unset. |
| `IG_ACCESS_TOKEN` | `instaselftool` | Token to use for Instagram (optional; overrides `FB_ACCESS_TOKEN`). |
| `FB_APP_TOKEN` | `fbselftool` | Optional `APP_ID\|APP_SECRET`, used by the **Token info** option, since `/debug_token` is meant to be called with an app token. Keep your app secret off shared machines and out of version control. |

All are optional — if the relevant token variable is unset, the tool prompts
for the token at startup.

---

## Running the tools

### Facebook

```bash
python -m fbselftool
```

Menu options:

```
[1] Show my profile (id + name)
[2] Show which permissions my token has
[3] List my own posts (read-only)
[4] Show my friend count
[5] Export a full backup to JSON (profile, posts, photos, videos)
[6] Token info — validity, scopes, expiry
[7] Pages I manage (post / insights / reply to comments)
[8] What's NOT possible, and why
[0] Exit
```

Everything about your personal account is **read-only**. The only write actions
are under **[7] Pages I manage** — posting, replying to comments, reading
insights for a Page you administer — and each asks for confirmation first. The
backup ([5]) writes `fb_backup_<timestamp>.json`; any section whose permission
your token lacks is skipped with a note.

### Instagram

```bash
python -m instaselftool
```

Menu options:

```
[1] Show my Instagram profile
[2] Export my media to a JSON backup
[3] Account insights
[4] Insights for one media item
[5] Read & reply to comments on one of my media
[6] Publish a photo (by public image URL)
[7] Publish a reel/video (by public video URL)
[8] Requirements & what's not possible
[0] Exit
```

At startup the tool finds the Instagram account(s) linked to your Pages and, if
there's more than one, lets you pick. Options [5]–[7] (replying, publishing) ask
for confirmation before they post. The backup ([2]) writes
`ig_backup_<timestamp>.json`.

---

## What's not possible

These were either in the original tool or are commonly expected, but the
official API does not allow them for a third-party app, so the tools **do not**
do them (and don't fake them):

- **Delete your own Facebook posts**, **unfriend**, **list all friends**, or
  **accept friend requests** — the relevant edges are read-only or were removed
  after Graph API v3.2; friend management isn't exposed.
- **Post to your personal Facebook timeline / upload a personal photo** —
  removed with the `publish_actions` permission in 2018. (Posting to a **Page**
  you manage *is* supported.)
- **Instagram publishing by local file** — the official endpoint fetches media
  from a **publicly reachable URL** you provide; videos are processed
  asynchronously (the tool waits for processing before publishing).
- **Anything on another person's account**, scraping, auto-follow/unfollow, or
  growth automation.

The original project did some of these by impersonating the Facebook Android
app (spoofed user-agent + hard-coded app token), which breaks Facebook's
Platform Terms. This rebuild removed all of it. For the actions the API can't
do, use the Facebook/Instagram website or app directly.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| `Could not authenticate with that token` | Token is wrong, expired (Explorer tokens last ~1h), or for the wrong app. Generate a fresh one. |
| A feature says it was "skipped" / returns nothing | Your token is missing that scope, or the scope isn't approved yet (App Review). Add it in the Graph API Explorer. |
| `No Instagram Professional account found` | Your IG account isn't a Business/Creator account, isn't linked to a Page, or the token lacks `pages_show_list` / `instagram_basic`. |
| **Token info** says an app token is required | Set `FB_APP_TOKEN="APP_ID\|APP_SECRET"` and retry. |
| Instagram publish fails on the image/video URL | The URL must be **public** (Instagram fetches it). Localhost or auth-gated URLs won't work. |
| `No space left` / permission errors writing a backup | Pick a writable path when prompted for the backup filename. |

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

requirements.txt   dependencies (requests)
```

---

## What was removed from the original project

The old Python 2 scripts were deleted entirely — nothing was ported or
referenced:

- **Password brute-forcing / "account cloning" / login guessing** — account
  takeover; illegal and abusive.
- **Harvesting other people's IDs, emails, and phone numbers** from friend
  lists — scraping third parties' personal data.
- **Impersonating the Facebook Android app** — spoofed user-agent and a
  hard-coded app token against a private endpoint.
- **Plaintext `login.txt` token storage** and **auto `pip install` / `rm -rf`**
  — replaced with in-memory tokens and no automatic install/delete.

---

## Legal

Use these only on your own accounts, with your own token. You are responsible
for complying with Facebook's and Instagram's
[Platform Terms](https://developers.facebook.com/terms/) and all applicable
laws. These tools are provided as-is, with no warranty.
