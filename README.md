---
title: I PAY Telegram Bot
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
---

# I PAY Telegram Bot

Telegram bot matching the supplied I PAY layout:

- Welcome message + inline menus
- New-member welcome
- PAYIN / PAYOUT wallet menus
- Events & announcements
- Security tips + FAQ
- Support links
- User registration and profile
- Referral links and referral earnings
- Admin statistics
- Admin broadcast
- Image-based issue guides
- SQLite storage
- Render webhook deployment
- Polling mode for local testing
- Hugging Face Spaces Docker deployment

## Important

Never commit your BotFather token, admin secrets, or other credentials to GitHub.

## 1. Create the Telegram bot

1. Open @BotFather in Telegram.
2. Create a bot with `/newbot`.
3. Copy the token.
4. Put it in your host's secret settings as `BOT_TOKEN`.

Do not put the token in GitHub.

## 2. Get your Telegram numeric ID

Use a trusted Telegram ID utility/bot or temporarily log the ID from your own bot.
Set it as:

`ADMIN_IDS=123456789`

For multiple admins:

`ADMIN_IDS=123456789,987654321`

## 3. GitHub

Create a new repository and upload:

- bot.py
- photo_*.jpg
- requirements.txt
- render.yaml
- .python-version
- .gitignore
- README.md

Do not upload `.env` or `ipay.db`.

## 4. Hugging Face Spaces

This repository includes a Docker Space setup. Hugging Face currently requires a PRO plan for personal accounts to create Docker Spaces. CPU Basic has no hourly compute charge, but the account plan is still required.

1. Sign in at Hugging Face and create a new Space with the Docker SDK.
2. Choose a Space name and visibility. Private is recommended because a public Space exposes its source code.
3. Upload or push `bot.py`, `Dockerfile`, `README.md`, `requirements.txt`, and the `photo_*.jpg` files. Do not upload `.env` or `ipay.db`.
4. In the Space's **Settings**, add the secrets and variables below.
5. Wait for the Docker build to finish, then check the Space's **Logs** for `Starting polling mode.`

The Space reads `BOT_TOKEN` from its secret settings and starts the bot in polling mode. Do not set `WEBHOOK_URL` for this deployment.

In the Space's **Settings**, add:

- Secret `BOT_TOKEN`: your current BotFather token
- Variable `ADMIN_IDS`: your Telegram numeric user ID (comma-separated for multiple admins)

Optional variables include `CHANNEL_URL`, `GROUP_URL`, `START_NOW_URL`, `COMMISSION`, `REFERRER_REWARD`, and `REFERRED_REWARD`.

The SQLite database is stored inside the container by default and can be lost when the Space restarts or rebuilds. For persistent data, attach a Hugging Face Storage Bucket to `/data` and set the Space variable `DB_PATH` to `/data/ipay.db`.

Free CPU Spaces can sleep after 48 hours of inactivity. A sleeping Space stops the bot until it wakes. Choose paid hardware if the bot must stay available continuously.

## 5. Render

Create a new Web Service connected to the GitHub repository.

The included `render.yaml` can also be used as a Blueprint.

Set these environment variables in Render:

- `BOT_TOKEN`
- `ADMIN_IDS`
- `WEBHOOK_URL`

The other values are already supplied in `render.yaml`.

After the Render service is created, copy its public URL, for example:

`https://ipay-telegram-bot.onrender.com`

Set:

`WEBHOOK_URL=https://ipay-telegram-bot.onrender.com`

Then redeploy.

## 6. Telegram permissions

For new-member welcomes in your group:

- Add the bot to the group.
- Give it permission to send messages.
- If Telegram requires it for the update types you use, make it an administrator.

For channel-management features, give the bot only the permissions it actually needs.

## 7. Test

Open the bot and send:

`/start`

Then test:

- WALLETS
- PAYIN
- PAYOUT
- ISSUES (order locked, slow withdrawal, UPI/wallet locked, payment notice)
- SECURITY
- FAQ
- SUPPORT
- PROFILE
- REFERRAL

## 8. Admin commands

`/admin`

`/stats`

`/users`

`/broadcast Your announcement`

Only IDs listed in `ADMIN_IDS` can use admin commands.

## Referral system

A user receives a personal link like:

`https://t.me/YourBot?start=ref_AB12CD34`

When a new Telegram user starts the bot using that link, the referral is recorded.

The referral reward defaults to ₹50 for the referrer and ₹100 for the referred user in configuration. The current code records the referrer's reward in the database; if you want automatic credit to the referred user's balance or a withdrawal ledger, add a wallet/transaction module before treating those amounts as withdrawable.

## Storage

The bot uses SQLite (`ipay.db`). SQLite is fine for a small bot, but if you need persistent production storage on Render, use an external database or an appropriate persistent storage setup. Do not assume a redeploy preserves a local SQLite file.

## Layout mapping

Main menu:
- 💰 WALLETS
- ❗ ISSUES
- 🛡️ SECURITY
- 💬 SUPPORT
- 👤 PROFILE
- 🤝 REFERRAL
- 🚀 START NOW

Wallet submenu:
- 💳 PAYIN
- 💸 PAYOUT

Security submenu:
- 🛡️ SECURITY TIPS
- ❓ FAQ

Navigation:
- ◀️ BACK
- 🏠 HOME


## Render troubleshooting / fixed mode

This version deliberately uses Telegram long polling instead of a Telegram webhook.
You do **not** need `WEBHOOK_URL`. On startup it removes any old webhook, connects to
Telegram, logs the bot username, and starts polling. Render only needs the bot token
(and optional admin ID) as secrets.

Required Render environment variables:
- `BOT_TOKEN` — BotFather token
- `ADMIN_IDS` — your numeric Telegram ID, if you want admin commands

Do not set `WEBHOOK_URL` for this version.
