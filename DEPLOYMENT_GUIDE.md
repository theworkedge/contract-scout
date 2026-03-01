# Contract Scout — Railway Deployment Guide

Deploy Contract Scout to Railway so it runs automatically every day at **8:00 AM EST**
(scheduled as `0 13 * * *` UTC).

---

## Prerequisites

- Railway account at [railway.app](https://railway.app)
- Repository pushed to GitHub (`theworkedge/contract-scout`)
- Railway CLI installed at `~/.local/bin/railway`
  - Add to PATH if not already: `export PATH="$HOME/.local/bin:$PATH"`

---

## Step 1 — Log in to Railway

```bash
~/.local/bin/railway login
```

This opens a browser window. Authenticate with your GitHub account.

---

## Step 2 — Create a new Railway project

```bash
cd "/Users/dperez7390/Library/CloudStorage/Dropbox/Mac (2)/Documents/Local Code Repository/contract-scout"
~/.local/bin/railway init
```

- Choose **"Empty Project"** when prompted
- Name it `contract-scout`

---

## Step 3 — Set environment variables

Railway runs in the cloud and has no access to your local `.env` file.
You must set all secrets via the CLI (or Railway dashboard).

```bash
~/.local/bin/railway variables set \
  SAM_API_KEY="your_sam_api_key_here" \
  ANTHROPIC_API_KEY="your_anthropic_api_key_here" \
  EMAIL_ADDRESS="your_gmail@gmail.com" \
  EMAIL_APP_PASSWORD="your_gmail_app_password_here" \
  RECIPIENT_EMAIL="recipient@example.com" \
  RECIPIENT_NAME="Dan"
```

> **Tip:** Find your values in the local `.env` file. Never commit `.env` to Git.

Verify variables were saved:

```bash
~/.local/bin/railway variables
```

---

## Step 4 — Deploy

```bash
~/.local/bin/railway up
```

Railway will build the project using Nixpacks (auto-detects Python from `runtime.txt`),
install dependencies from `requirements.txt`, and deploy the cron worker.

---

## Step 5 — Verify the cron schedule

1. Open the Railway dashboard: `~/.local/bin/railway open`
2. Select your service → **Settings** → **Cron Schedule**
3. Confirm the schedule shows `0 13 * * *` (8:00 AM EST / 13:00 UTC)

---

## Step 6 — Test immediately (optional but recommended)

Run Contract Scout right now on Railway without waiting for the cron trigger:

```bash
~/.local/bin/railway run python3 contract_scout.py
```

Check logs:

```bash
~/.local/bin/railway logs
```

You should see output ending with `=== Contract Scout finished ===` and receive an email.

---

## Cron Schedule Reference

| UTC Time | EST Time | Cron Expression |
|----------|----------|-----------------|
| 13:00    | 08:00 AM | `0 13 * * *`    |

> **Note:** Railway always uses UTC for cron. EST = UTC−5. During EDT (summer) = UTC−4,
> so the job will run at 9:00 AM EDT. Adjust to `0 12 * * *` in `railway.toml` if needed.

---

## Updating the deployment

After making code changes locally:

```bash
git add -A && git commit -m "Your change description"
git push origin main
~/.local/bin/railway up
```

---

## Disabling Railway (if switching back to local LaunchAgent)

```bash
# Suspend the Railway service from the dashboard, or delete the project:
~/.local/bin/railway service delete
```

To re-enable the local LaunchAgent:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theworkedge.contractscout.plist
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Missing env vars` error | Re-run Step 3; check `railway variables` |
| Build fails | Check `runtime.txt` says `python-3.11` and `requirements.txt` is complete |
| No email received | Check `EMAIL_APP_PASSWORD` is a Gmail App Password (not your login password) |
| Wrong run time | Verify `railway.toml` has `cronSchedule = "0 13 * * *"` |
| CLI not found | Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.zshrc` |
