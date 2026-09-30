import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------
# Configuration
# ----------------------------
env_file = Path(__file__).with_name(".env")
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/Ipay_Official_Channel")
GROUP_URL = os.getenv("GROUP_URL", "https://t.me/ipayvip_1")
START_NOW_URL = os.getenv("START_NOW_URL", "https://share.ipaynow.net/?data=dWlkPTg5NDIzNSZjaGFubmVsPTEwMDEmYnVzaW5lc3NfaWQ9OTAwMDAy")
COMMISSION = os.getenv("COMMISSION", "4%")
DB_PATH = os.getenv("DB_PATH", "ipay.db")
BOT_DIR = Path(__file__).resolve().parent
SCREEN_IMAGES = {
    "welcome": "photo_2026-09-06_13-45-50.jpg",
    "wallets": "photo_2026-09-30_19-47-27.jpg",
    "payout": "photo_2026-09-30_19-47-44.jpg",
    "security": "photo_2026-09-30_19-47-48.jpg",
    "issue_order": "photo_2026-09-30_19-47-53.jpg",
    "issue_upi": "photo_2026-09-30_19-47-46.jpg",
    "issue_notice": "photo_2026-09-30_19-47-48.jpg",
}

# Referral values are configurable; change them in Render Environment Variables.
REFERRER_REWARD = float(os.getenv("REFERRER_REWARD", "50"))
REFERRED_REWARD = float(os.getenv("REFERRED_REWARD", "100"))

PAYIN_WALLETS = ["Paytm", "PhonePe", "MobiKwik", "Freecharge"]
PAYOUT_WALLETS = [
    "Paytm",
    "PhonePe",
    "MobiKwik",
    "Google Pay Business",
    "BharatPe Business",
    "Paytm Business",
]

SECURITY_TEXT = (
    "🛡️ <b>SECURITY TIPS</b>\n\n"
    "🔐 Never share your password or OTP.\n"
    "🔒 Keep your account information secure.\n"
    "🚫 Never share sensitive account details with unknown persons.\n"
    "✅ Verify official I PAY support accounts before responding.\n"
    "⚠️ Be careful of fake accounts, links and scams."
)

FAQ_TEXT = (
    "❓ <b>FREQUENTLY ASKED QUESTIONS</b>\n\n"
    "• <b>How do I start?</b>\n"
    "Use /start and choose an option from the main menu.\n\n"
    "• <b>What wallets are supported?</b>\n"
    "See the PAYIN and PAYOUT sections for the current lists.\n\n"
    "• <b>How do I get support?</b>\n"
    "Use the Support menu to open the support group/contact.\n\n"
    "• <b>Where can I see my referral details?</b>\n"
    "Open 👤 Profile from the main menu."
)

# ----------------------------
# Database
# ----------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by INTEGER,
                referral_earnings REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


def make_referral_code():
    return secrets.token_hex(4).upper()


def register_user(tg_user, referred_by=None):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE id=?", (tg_user.id,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=? WHERE id=?",
                (tg_user.username, tg_user.first_name, now, tg_user.id),
            )
            conn.commit()
            return False, existing["referral_code"], existing["referred_by"]

        code = make_referral_code()
        while conn.execute(
            "SELECT 1 FROM users WHERE referral_code=?", (code,)
        ).fetchone():
            code = make_referral_code()

        valid_referrer = None
        if referred_by and referred_by != tg_user.id:
            ref = conn.execute(
                "SELECT id FROM users WHERE id=?", (referred_by,)
            ).fetchone()
            if ref:
                valid_referrer = referred_by

        conn.execute(
            """
            INSERT INTO users
            (id, username, first_name, referral_code, referred_by, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tg_user.id,
                tg_user.username,
                tg_user.first_name,
                code,
                valid_referrer,
                now,
                now,
            ),
        )

        # Referral credit is recorded only when the referred user is newly registered.
        if valid_referrer:
            conn.execute(
                "UPDATE users SET referral_earnings=referral_earnings+? WHERE id=?",
                (REFERRER_REWARD, valid_referrer),
            )

        conn.commit()
        return True, code, valid_referrer


def get_user(user_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id=?", (user_id,)
        ).fetchone()


def user_count():
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def referral_count(user_id):
    with db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)
        ).fetchone()[0]


def get_all_user_ids():
    with db() as conn:
        return [r[0] for r in conn.execute("SELECT id FROM users").fetchall()]


# ----------------------------
# UI
# ----------------------------
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 WALLETS", callback_data="wallets"),
            InlineKeyboardButton("❗ ISSUES", callback_data="issues"),
        ],
        [
            InlineKeyboardButton("🛡️ SECURITY", callback_data="security"),
            InlineKeyboardButton("💬 SUPPORT", callback_data="support"),
        ],
        [
            InlineKeyboardButton("👤 PROFILE", callback_data="profile"),
            InlineKeyboardButton("🤝 REFERRAL", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🚀 START NOW ↗", url=START_NOW_URL),
        ],
    ])


def home_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 WALLETS", callback_data="wallets"),
            InlineKeyboardButton("❗ ISSUES", callback_data="issues"),
        ],
        [
            InlineKeyboardButton("🛡️ SECURITY", callback_data="security"),
            InlineKeyboardButton("💬 SUPPORT", callback_data="support"),
        ],
        [
            InlineKeyboardButton("👤 PROFILE", callback_data="profile"),
            InlineKeyboardButton("🤝 REFERRAL", callback_data="referral"),
        ],
        [InlineKeyboardButton("🚀 START NOW ↗", url=START_NOW_URL)],
    ])


def back_home():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ BACK", callback_data="home"),
            InlineKeyboardButton("🏠 HOME", callback_data="home"),
        ]
    ])


def wallet_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 PAYIN", callback_data="payin"),
            InlineKeyboardButton("💸 PAYOUT", callback_data="payout"),
        ],
        [
            InlineKeyboardButton("◀️ BACK", callback_data="home"),
            InlineKeyboardButton("🏠 HOME", callback_data="home"),
        ],
    ])


def issues_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Order locked", callback_data="issue_order")],
        [InlineKeyboardButton("⏳ Withdrawal is slow", callback_data="issue_withdrawal")],
        [InlineKeyboardButton("🔐 UPI / wallet locked", callback_data="issue_upi")],
        [InlineKeyboardButton("📋 Payment notice", callback_data="issue_notice")],
        [InlineKeyboardButton("◀️ BACK", callback_data="home"),
         InlineKeyboardButton("🏠 HOME", callback_data="home")],
    ])


def security_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛡️ SECURITY TIPS", callback_data="security_tips"),
            InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        ],
        [
            InlineKeyboardButton("◀️ BACK", callback_data="home"),
            InlineKeyboardButton("🏠 HOME", callback_data="home"),
        ],
    ])


def support_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💼 CUSTOMER SERVICE", url=GROUP_URL)],
        [InlineKeyboardButton("👥 SUPPORT GROUP", url=GROUP_URL)],
        [
            InlineKeyboardButton("◀️ BACK", callback_data="home"),
            InlineKeyboardButton("🏠 HOME", callback_data="home"),
        ],
    ])


async def render_callback(q, context, text, reply_markup, image_key=None):
    image_path = BOT_DIR / SCREEN_IMAGES[image_key] if image_key else None
    if image_path and not image_path.is_file():
        logging.warning("Screen image is missing: %s", image_path.name)
        image_path = None
    if image_key == "welcome" and image_path is None and text is None:
        text = "Welcome image is unavailable."

    if q.message.photo:
        if image_path:
            with image_path.open("rb") as photo:
                await q.edit_message_media(
                    media=InputMediaPhoto(
                        media=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML if text else None,
                    ),
                    reply_markup=reply_markup,
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=20,
                    pool_timeout=20,
                )
        else:
            await q.message.delete()
            await context.bot.send_message(
                chat_id=q.message.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
    elif image_path:
        await q.message.delete()
        with image_path.open("rb") as photo:
            await context.bot.send_photo(
                chat_id=q.message.chat_id,
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML if text else None,
                reply_markup=reply_markup,
                read_timeout=60,
                write_timeout=60,
                connect_timeout=20,
                pool_timeout=20,
            )
    else:
        await q.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=reply_markup
        )


async def send_welcome_image(message):
    image_path = BOT_DIR / SCREEN_IMAGES["welcome"]
    if image_path.is_file():
        try:
            with image_path.open("rb") as photo:
                await message.reply_photo(
                    photo=photo,
                    reply_markup=main_menu(),
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=20,
                    pool_timeout=20,
                )
        except (TimedOut, NetworkError):
            logging.warning("Welcome image upload timed out; sending text fallback.")
            await message.reply_text(
                "Welcome to I PAY", reply_markup=main_menu()
            )
    else:
        logging.error("Welcome image is missing: %s", image_path.name)
        await message.reply_text(
            "Welcome to I PAY", reply_markup=main_menu()
        )


# ----------------------------
# Commands
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None

    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            code = arg[4:].upper()
            with db() as conn:
                row = conn.execute(
                    "SELECT id FROM users WHERE referral_code=?", (code,)
                ).fetchone()
                if row:
                    referred_by = row["id"]

    register_user(user, referred_by)
    await send_welcome_image(update.message)


async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    row = get_user(user.id)
    refs = referral_count(user.id)
    link = f"https://t.me/{context.bot.username}?start=ref_{row['referral_code']}"
    text = (
        "👤 <b>MY PROFILE</b>\n\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n"
        f"👤 Name: {user.first_name or '-'}\n"
        f"🔗 Referral code: <code>{row['referral_code']}</code>\n"
        f"👥 Successful referrals: <b>{refs}</b>\n"
        f"💰 Referral earnings: <b>₹{row['referral_earnings']:.2f}</b>\n\n"
        f"📎 <b>Your referral link:</b>\n{link}"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=back_home()
    )


# ----------------------------
# Callback menus
# ----------------------------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    register_user(user)

    data = q.data

    if data == "home":
        await render_callback(
            q, context, None, home_buttons(), image_key="welcome"
        )

    elif data == "wallets":
        await render_callback(
            q, context,
            "💰 <b>WALLET CENTER</b>\n\nSelect the service you need:",
            wallet_menu(),
            image_key="wallets",
        )

    elif data == "payin":
        wallets = "\n".join(f"• {x}" for x in PAYIN_WALLETS)
        text = (
            "💳 <b>PAYIN</b>\n\n"
            "<b>Supported Wallets:</b>\n" + wallets +
            "\n\nPlease use only the currently supported payment methods."
        )
        await render_callback(q, context, text, back_home())

    elif data == "payout":
        wallets = "\n".join(f"• {x}" for x in PAYOUT_WALLETS)
        text = (
            "💸 <b>PAYOUT</b>\n\n"
            "<b>Supported Wallets:</b>\n" + wallets +
            "\n\nUse supported business wallets for a faster and smoother experience."
        )
        await render_callback(q, context, text, back_home(), image_key="payout")

    elif data == "issues":
        await render_callback(
            q, context, "❗ <b>ISSUES</b>\n\nChoose the issue you need help with:",
            issues_menu(),
        )

    elif data == "issue_order":
        await render_callback(
            q, context,
            "🔒 <b>ORDER LOCKED</b>\n\nReview the steps in this guide. For account-specific help, contact official support.",
            back_home(), image_key="issue_order",
        )

    elif data == "issue_withdrawal":
        await render_callback(
            q, context,
            "⏳ <b>WITHDRAWAL IS SLOW</b>\n\nReview these checks. For account-specific status, contact official support.",
            back_home(), image_key="payout",
        )

    elif data == "issue_upi":
        await render_callback(
            q, context,
            "🔐 <b>UPI OR WALLET LOCKED</b>\n\nReview your wallet provider's guidance and contact them if the restriction remains.",
            back_home(), image_key="issue_upi",
        )

    elif data == "issue_notice":
        await render_callback(
            q, context,
            "📋 <b>PAYMENT NOTICE</b>\n\nReview the payment instructions before completing an order.",
            back_home(), image_key="issue_notice",
        )

    elif data == "security":
        await render_callback(
            q, context,
            "🛡️ <b>SECURITY & FAQ</b>\n\nChoose an option below:",
            security_menu(),
        )

    elif data == "security_tips":
        await render_callback(
            q, context, SECURITY_TEXT, back_home(), image_key="security"
        )

    elif data == "faq":
        await render_callback(q, context, FAQ_TEXT, back_home())

    elif data == "support":
        await render_callback(
            q, context,
            "💬 <b>CUSTOMER SUPPORT</b>\n\n"
            "Our support team is ready to assist you.\n\n"
            "Choose an option below:",
            support_menu(),
        )

    elif data == "profile":
        row = get_user(user.id)
        refs = referral_count(user.id)
        link = f"https://t.me/{context.bot.username}?start=ref_{row['referral_code']}"
        text = (
            "👤 <b>MY PROFILE</b>\n\n"
            f"🆔 Telegram ID: <code>{user.id}</code>\n"
            f"👤 Name: {user.first_name or '-'}\n"
            f"🔗 Referral code: <code>{row['referral_code']}</code>\n"
            f"👥 Successful referrals: <b>{refs}</b>\n"
            f"💰 Referral earnings: <b>₹{row['referral_earnings']:.2f}</b>\n\n"
            f"📎 <b>Your referral link:</b>\n{link}"
        )
        await render_callback(q, context, text, back_home())

    elif data == "referral":
        row = get_user(user.id)
        refs = referral_count(user.id)
        link = f"https://t.me/{context.bot.username}?start=ref_{row['referral_code']}"
        text = (
            "🤝 <b>REFERRAL PROGRAM</b>\n\n"
            f"Invite friends using your personal referral link.\n\n"
            f"👥 Referrals: <b>{refs}</b>\n"
            f"💰 Referral earnings: <b>₹{row['referral_earnings']:.2f}</b>\n\n"
            f"🔗 <code>{link}</code>"
        )
        await render_callback(q, context, text, back_home())


# ----------------------------
# Group new-member welcome
# ----------------------------
async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        register_user(member)
        await send_welcome_image(update.message)


async def mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If someone mentions the bot in a normal group message, show a compact menu.
    if not update.message or not update.message.text:
        return
    bot_username = context.bot.username
    if bot_username and f"@{bot_username.lower()}" in update.message.text.lower():
        register_user(update.effective_user)
        await send_welcome_image(update.message)


# ----------------------------
# Admin
# ----------------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🛠️ <b>ADMIN COMMANDS</b>\n\n"
        "/stats — user statistics\n"
        "/broadcast Your message — broadcast to registered users\n"
        "/users — show registered user count",
        parse_mode=ParseMode.HTML,
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"📊 <b>I PAY BOT STATISTICS</b>\n\n"
        f"👥 Registered users: <b>{user_count()}</b>",
        parse_mode=ParseMode.HTML,
    )


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stats(update, context)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /broadcast Your message here"
        )
        return

    message = " ".join(context.args)
    ids = get_all_user_ids()
    sent = 0
    failed = 0

    for user_id in ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception as exc:
            logging.warning("Broadcast failed for %s: %s", user_id, exc)
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast complete.\n\n✅ Sent: {sent}\n❌ Failed: {failed}"
    )


# ----------------------------
# Health / webhook server
# ----------------------------
def start_health_server(port):
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/health"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logging.info("Health server listening on port %s", port)


def build_application():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", my_profile))
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, mentioned)
    )

    return app


def main():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = build_application()

    port = int(os.getenv("PORT", "7860" if os.getenv("SPACE_ID") else "10000"))
    if os.getenv("SPACE_ID"):
        start_health_server(port)

    # Set WEBHOOK_URL for Render. Hugging Face Spaces uses polling.
    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")

    if webhook_url:
        logging.info("Starting Telegram webhook on port %s", port)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram",
            webhook_url=f"{webhook_url}/telegram",
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logging.info("Starting polling mode.")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    main()
