import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Conflict, InvalidToken, NetworkError, TimedOut
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
CUSTOMER_SERVICE_URL = os.getenv("CUSTOMER_SERVICE_URL", "https://t.me/ipay800")
START_NOW_URL = os.getenv("START_NOW_URL", "https://share.ipaynow.net/?data=dWlkPTg5NDIzNSZjaGFubmVsPTEwMDEmYnVzaW5lc3NfaWQ9OTAwMDAy")
COMMISSION = os.getenv("COMMISSION", "4%")
WELCOME_CAPTION = (
    "🪐WELCOME TO <b>iPAY</b>\n"
    "━━━━━━━━━━━━━━\n\n"
    f"📌 {COMMISSION} commission on deposits\n"
    "🎁 Rs 5 activity reward\n\n"
    "⚡ Fast, smooth, and easy\n"
    "⏩ Choose an option to get started"
)
DB_PATH = os.getenv("DB_PATH", "ipay.db")
BOT_DIR = Path(__file__).resolve().parent
if not Path(DB_PATH).is_absolute():
    DB_PATH = str(BOT_DIR / DB_PATH)
SCREEN_IMAGES = {
    "welcome": "photo_2026-09-06_13-45-50.jpg",
    "wallets": "photo_2026-09-30_19-47-27.jpg",
    "payout": "photo_2026-09-30_19-47-44.jpg",
    "security": "photo_2026-09-30_19-47-48.jpg",
    "issue_order": "photo_2026-09-30_19-47-53.jpg",
    "issue_upi": "photo_2026-09-30_19-47-46.jpg",
    "issue_notice": "photo_2026-09-30_19-47-48.jpg",
    "referral": "photo_2026-09-30_19-47-36.jpg",
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
    "🛡️ <b>iPAY SECURITY TIPS</b>\n\n"
    "🔐 Never share your OTP, password, or UPI PIN with anyone, including support.\n"
    "💸 You do not need to enter your UPI PIN to receive money.\n"
    "🔎 Check the recipient and amount carefully before confirming a payment.\n"
    "🔗 Avoid suspicious links and never share screen access or banking details.\n"
    "✅ Contact support only through the links in this bot.\n"
    "⚠️ If a payment looks suspicious, contact your bank promptly and report it to support."
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
    "Open Referral from the main menu."
)

# ----------------------------
# Database
# ----------------------------
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media_cache (
                image_key TEXT PRIMARY KEY,
                telegram_file_id TEXT NOT NULL
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


def get_cached_image_id(image_key):
    with db() as conn:
        row = conn.execute(
            "SELECT telegram_file_id FROM media_cache WHERE image_key=?",
            (image_key,),
        ).fetchone()
        return row["telegram_file_id"] if row else None


def cache_sent_image(image_key, message):
    photos = getattr(message, "photo", None)
    if not photos:
        return
    with db() as conn:
        conn.execute(
            "INSERT INTO media_cache(image_key,telegram_file_id) VALUES(?,?) "
            "ON CONFLICT(image_key) DO UPDATE SET telegram_file_id=excluded.telegram_file_id",
            (image_key, photos[-1].file_id),
        )


def clear_cached_image(image_key):
    with db() as conn:
        conn.execute("DELETE FROM media_cache WHERE image_key=?", (image_key,))


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
            InlineKeyboardButton("🤝 REFERRAL", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🚀 START NOW ↗", url=START_NOW_URL),
        ],
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
        [InlineKeyboardButton("👨‍💼 CUSTOMER SERVICE", url=CUSTOMER_SERVICE_URL)],
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

    try:
        if q.message.photo:
            if image_path:
                file_id = get_cached_image_id(image_key)
                if file_id:
                    try:
                        edited = await q.edit_message_media(
                            media=InputMediaPhoto(
                                media=file_id,
                                caption=text,
                                parse_mode=ParseMode.HTML if text else None,
                            ),
                            reply_markup=reply_markup,
                        )
                    except BadRequest:
                        clear_cached_image(image_key)
                        file_id = None
                if not file_id:
                    with image_path.open("rb") as photo:
                        edited = await q.edit_message_media(
                            media=InputMediaPhoto(
                                media=photo,
                                caption=text,
                                parse_mode=ParseMode.HTML if text else None,
                            ),
                            reply_markup=reply_markup,
                            read_timeout=30,
                            write_timeout=30,
                            connect_timeout=10,
                            pool_timeout=10,
                        )
                    cache_sent_image(image_key, edited)
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
            file_id = get_cached_image_id(image_key)
            if file_id:
                try:
                    sent = await context.bot.send_photo(
                        chat_id=q.message.chat_id,
                        photo=file_id,
                        caption=text,
                        parse_mode=ParseMode.HTML if text else None,
                        reply_markup=reply_markup,
                    )
                except BadRequest:
                    clear_cached_image(image_key)
                    file_id = None
            if not file_id:
                with image_path.open("rb") as photo:
                    sent = await context.bot.send_photo(
                        chat_id=q.message.chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML if text else None,
                        reply_markup=reply_markup,
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=10,
                        pool_timeout=10,
                    )
                cache_sent_image(image_key, sent)
        else:
            await q.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
    except NetworkError as exc:
        logging.warning("Image screen failed (%s); falling back to text.", type(exc).__name__)
        if q.message.photo:
            try:
                await q.message.delete()
            except NetworkError:
                pass
        await context.bot.send_message(
            chat_id=q.message.chat_id,
            text=text or "Welcome to I PAY",
            parse_mode=ParseMode.HTML if text else None,
            reply_markup=reply_markup,
        )


async def send_welcome_image(message):
    image_path = BOT_DIR / SCREEN_IMAGES["welcome"]
    if image_path.is_file():
        try:
            file_id = get_cached_image_id("welcome")
            if file_id:
                try:
                    sent = await message.reply_photo(
                        photo=file_id,
                        caption=WELCOME_CAPTION,
                        parse_mode=ParseMode.HTML,
                        reply_markup=main_menu(),
                    )
                except BadRequest:
                    clear_cached_image("welcome")
                    file_id = None
            if not file_id:
                with image_path.open("rb") as photo:
                    sent = await message.reply_photo(
                        photo=photo,
                        caption=WELCOME_CAPTION,
                        parse_mode=ParseMode.HTML,
                        reply_markup=main_menu(),
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=10,
                        pool_timeout=10,
                    )
                cache_sent_image("welcome", sent)
        except (TimedOut, NetworkError):
            logging.warning("Welcome image upload timed out; sending text fallback.")
            await message.reply_text(
                WELCOME_CAPTION, parse_mode=ParseMode.HTML,
                reply_markup=main_menu()
            )
    else:
        logging.error("Welcome image is missing: %s", image_path.name)
        await message.reply_text(
            WELCOME_CAPTION, parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
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
            q, context, WELCOME_CAPTION, main_menu(), image_key="welcome"
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

    elif data == "referral":
        row = get_user(user.id)
        refs = referral_count(user.id)
        link = f"https://t.me/{context.bot.username}?start=ref_{row['referral_code']}"
        text = (
            "🤝 <b>INVITE FRIENDS, SHARE REWARDS</b>\n\n"
            f"👥 People registered: <b>{refs}</b>\n"
            f"💰 Recorded referral earnings: <b>₹{row['referral_earnings']:.2f}</b>\n\n"
            f"🔗 <b>Your personal referral link:</b>\n<code>{escape(link)}</code>"
        )
        text += (
            "\n\n<b>How to qualify</b>\n"
            "1. Share your personal referral link.\n"
            "2. A new user must open your link and tap Start.\n"
            f"3. After their first registration, Rs {REFERRER_REWARD:g} referral credit is recorded for you.\n\n"
            "Existing users do not count as new referrals. This bot does not require an order or deposit for this credit."
        )
        await render_callback(q, context, text, back_home(), image_key="referral")


# ----------------------------
# Group new-member welcome
# ----------------------------
async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcomed = False
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        register_user(member)
        welcomed = True
    if welcomed:
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
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, mentioned)
    )
    app.add_error_handler(handle_error)

    return app


async def handle_error(update, context):
    error = context.error
    if isinstance(error, Conflict):
        logging.error(
            "Telegram polling conflict: another bot process or an active webhook is using this token."
        )
        return
    logging.error("Update handler failed (%s).", type(error).__name__)
    if isinstance(error, NetworkError) or not update or not update.effective_message:
        return
    try:
        await update.effective_message.reply_text(
            "Sorry, something went wrong. Please try again or contact support."
        )
    except Exception:
        pass


def main():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = build_application()

    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    port = int(os.getenv("PORT", "7860" if os.getenv("SPACE_ID") else "10000"))
    if os.getenv("SPACE_ID") or (os.getenv("RENDER") and not webhook_url):
        start_health_server(port)

    try:
        if webhook_url:
            logging.info("Starting Telegram webhook on port %s", port)
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path="telegram",
                webhook_url=f"{webhook_url}/telegram",
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES,
            )
        else:
            logging.info("Starting polling mode.")
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )
    except InvalidToken:
        logging.critical(
            "Telegram rejected BOT_TOKEN. Create a fresh token with BotFather; its value was suppressed."
        )


if __name__ == "__main__":
    main()
