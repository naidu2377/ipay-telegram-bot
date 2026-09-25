import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
START_NOW_URL = "https://share.ipaynow.net/?data=dWlkPTg5NDIzNSZjaGFubmVsPTEwMDEmYnVzaW5lc3NfaWQ9OTAwMDAy"
CUSTOMER_SERVICE_URL = "https://t.me/Ipay800"

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 WALLETS", callback_data="wallets"),
         InlineKeyboardButton("🎉 EVENTS", callback_data="events")],
        [InlineKeyboardButton("🛡️ SECURITY", callback_data="security"),
         InlineKeyboardButton("💬 SUPPORT", url=CUSTOMER_SERVICE_URL)],
        [InlineKeyboardButton("🚀 START NOW", url=START_NOW_URL)]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💚 <b>WELCOME TO I PAY</b> 💚\n\n"
        "💰 <b>4% Commission</b>\n"
        "⚡ Fast & Smooth Transactions\n"
        "🎁 Exciting Rewards\n"
        "💙 Professional Support\n\n"
        "👇 Choose an option below:",
        parse_mode="HTML", reply_markup=menu()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    texts={
        "wallets":"💰 <b>SUPPORTED WALLETS</b>\n\nPhonePe\nPaytm\nMobiKwik\nFreecharge\nAmazon Pay",
        "events":"🎉 <b>I PAY EVENTS</b>\n\nCheck I PAY for current rewards, campaigns and eligibility.",
        "security":"🛡️ <b>SECURITY</b>\n\nNever share your OTP, UPI PIN or password."
    }
    await q.edit_message_text(texts.get(q.data,"I PAY"), parse_mode="HTML",
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 HOME", callback_data="home")]]) if q.data!="home" else menu())

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
