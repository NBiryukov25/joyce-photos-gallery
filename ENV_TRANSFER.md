# Environment / Key Transfer Guide

How to copy your keys **out of Railway** and into another host (a new Railway
project, Render, Fly, or a local `.env`). The actual secret **values live only in
Railway** — they are not in this repo — so this guide is about moving them, not
storing them here.

> ⚠️ Never paste real key values into a file that gets committed. Use `.env`
> (already gitignored) or the destination host's secret manager. `.env.template`
> in this repo has the key **names** only.

---

## The keys this app uses

| Key | Used by | What it is / where it comes from | Copy over? |
|-----|---------|----------------------------------|:---------:|
| `TELEGRAM_BOT_TOKEN` | telegram_bot.py, local_bot.py | Bot token from **@BotFather** | ✅ |
| `TELEGRAM_ALLOWED_USER_ID` | telegram_bot.py, local_bot.py | Your Telegram user id (**@userinfobot**) | ✅ |
| `TELEGRAM_CHANNEL` | telegram_bot.py | Target channel id/handle | ✅ |
| `GITHUB_TOKEN` | telegram_bot.py, local_bot.py | GitHub **Personal Access Token** (repo write) | ✅ |
| `GITHUB_REPO` | telegram_bot.py, local_bot.py | `NBiryukov25/joyce-photos-gallery` | ✅ |
| `GITHUB_BRANCH` | telegram_bot.py, local_bot.py | `main` | ✅ |
| `AIRTABLE_TOKEN` | build_site.py | Airtable API token (data source) | ✅ |
| `ANTHROPIC_API_KEY` | telegram_bot.py | Claude API key | ✅ |
| `GROQ_API_KEY` | telegram_bot.py | Groq API key | ✅ |
| `TRANSCRIBE_API_TOKEN` | telegram_bot.py | Transcription service token | ✅ |
| `NETLIFY_SITE_URL` | telegram_bot.py | Netlify site URL for share links | ✅ |
| `SHARE_SECRET` | telegram_bot.py | Secret used to sign share links | ✅ |
| `PORT` | (all servers) | **Set automatically by the host** | ❌ don't copy |

`PORT` is injected by Railway/Render/Fly at runtime — do **not** copy it, or you
can break the deploy.

---

## Step 1 — Copy the values OUT of Railway

### Option A — Dashboard (easiest)
1. Open your project in Railway → select the **service** → **Variables** tab.
2. Click **Raw Editor** (top-right of the variables list).
3. It shows every variable as `KEY=value`, one per line. **Select all → copy.**
4. Paste into a scratch note (or straight into the destination's Raw Editor).

### Option B — Railway CLI
```bash
# one-time
npm i -g @railway/cli
railway login
railway link                 # pick the project + service

# print all variables as KEY=value
railway variables --kv       # copy this output

# …or write them straight to a local .env (never commit it)
railway variables --kv > .env
```

---

## Step 2 — Paste the values INTO the new host

### → A new Railway project
Service → **Variables** → **Raw Editor** → paste the `KEY=value` block → **Save**.
Remove the `PORT` line if it came along.

### → Render
- Dashboard: your service → **Environment** → **Add from .env** (or add each
  key) → paste → **Save Changes**. (`render.yaml` is already in this repo.)
- Do **not** add `PORT` — Render sets it.

### → Fly.io
```bash
# from a filled-in .env (PORT removed):
cat .env | grep -v '^PORT=' | grep -v '^#' | grep -v '^$' | xargs -I{} fly secrets set {}
```

### → Local development
```bash
cp .env.template .env     # then fill in the values, or use `railway variables --kv > .env`
python telegram_bot.py
```

---

## Step 3 — Verify

- Destination has **all 12** keys above (everything except `PORT`).
- No key value is empty.
- The bot starts without `KeyError`/`None` env errors.
- Rotate anything that was pasted into a chat or scratch doc during the move
  (especially `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `SHARE_SECRET`) if you want to
  be safe — most hosts let you regenerate and re-paste in minutes.

---

## Security notes
- The real values are **only** in your host's secret store — keep it that way.
- `.env` is gitignored; never force-add it.
- Treat a copied `KEY=value` block like a password list: don't email/DM it, and
  clear any scratch note when you're done.
