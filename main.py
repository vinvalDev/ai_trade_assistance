import logging
import asyncio
import csv
import os
import re
from datetime import datetime

import nest_asyncio
nest_asyncio.apply()

from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# Logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Bot token
BOT_TOKEN = "7910424385:AAHr0HoEyX07tDtL_oLaFSBN24QRQStWT3w"

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Write credentials JSON from env variable to file
with open("google_credentials.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS"])

credentials = Credentials.from_service_account_file("google_credentials.json", scopes=SCOPES)
gc = gspread.authorize(credentials)
user_sheets = {}

# In-memory fallback
trade_journal = []

# Utils
def parse_input(text):
    try:
        parts = dict(pair.split(":") for pair in text.split() if ":" in pair)
        return float(parts['capital']), float(parts['entry']), float(parts['sl']), float(parts['tp']), float(parts['lot'])
    except:
        return None

def calculate_metrics(capital, entry, sl, tp, lot):
    pip_value = 10 * lot
    risk_pips = abs(entry - sl) * 10000
    reward_pips = abs(tp - entry) * 10000
    risk_amount = risk_pips * pip_value
    reward_amount = reward_pips * pip_value
    risk_percent = (risk_amount / capital) * 100
    rr_ratio = reward_amount / risk_amount if risk_amount else 0
    return risk_amount, reward_amount, risk_percent, rr_ratio

# Handlers (same as before: riskcalc_handler, remind_handler, etc.)
# -- truncated for brevity but unchanged from your original --

# ⬇️ Add all handlers to the app inside main()
async def main():
    print("🤖 Bot is running...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("riskcalc", riskcalc_handler))
    app.add_handler(CommandHandler("remind", remind_handler))
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("journal", journal_handler))
    app.add_handler(CommandHandler("export", export_handler))
    app.add_handler(CommandHandler("linksheet", linksheet_handler))
    app.add_handler(CommandHandler("sheethelp", sheethelp_handler))
    app.add_handler(CommandHandler("feedback", feedback_handler))
    app.add_handler(CommandHandler("edittrade", edittrade_handler))
    app.add_handler(CommandHandler("privacy", privacy_handler))
    app.add_handler(CommandHandler("deletetrade", deletetrade_handler))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
