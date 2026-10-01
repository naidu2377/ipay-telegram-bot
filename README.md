---
title: I PAY Telegram Bot
colorFrom: blue
colorTo: yellow
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

## 4. Render

Create a new Web Service connected to the GitHub repository, or create it from the included Blueprint. The Blueprint uses Render's native Python runtime, installs `requirements.txt`, and starts the bot with `python bot.py`.

The included `render.yaml` can also be used as a Blueprint.

Set these environment variables in Render:

- `BOT_TOKEN`
- `ADMIN_IDS` (optional; required for admin commands)

The bot receives Telegram updates through long polling, so it does not need `WEBHOOK_URL`. The service also exposes a small health endpoint on Render's assigned `PORT`.

## 5. Telegram permissions

For new-member welcomes in your group:

- Add the bot to the group.
- Give it permission to send messages.
- If Telegram requires it for the update types you use, make it an administrator.

For channel-management features, give the bot only the permissions it actually needs.

## 6. Test

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

## 7. Admin commands

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
