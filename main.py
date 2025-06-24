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

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# Logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Bot token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

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

# /riskcalc
async def riskcalc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.replace('/riskcalc', '').strip()
    parsed = parse_input(msg)

    if not parsed:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n/riskcalc capital:1000 entry:1.0920 sl:1.0900 tp:1.0980 lot:0.5"
        )
        return

    capital, entry, sl, tp, lot = parsed
    risk_amount, reward_amount, risk_percent, rr_ratio = calculate_metrics(capital, entry, sl, tp, lot)

    warning = ""
    if risk_percent > 2:
        warning += "⚠️ Risk exceeds 2% of capital.\n"
    if rr_ratio < 1.5:
        warning += "⚠️ RR Ratio is below 1.5 — consider skipping.\n"

    cpa_msg = "\n🔗 *Recommended Broker*: [Sign up to Exness](https://one.exnesstrack.org/a/c_ctqfjsjmem?platform=mobile) for tighter spreads & fast execution."

    response = f"""
📊 *Trade Risk Summary*:
Capital: ${capital}
Entry: {entry}
Stop Loss: {sl}
Take Profit: {tp}
Lot Size: {lot}

📉 *Risk*: ${risk_amount:.2f} ({risk_percent:.2f}%)
📈 *Reward*: ${reward_amount:.2f}
⚖️ *RR Ratio*: 1:{rr_ratio:.2f}

{warning if warning else "✅ Risk & RR look solid!"}
{cpa_msg}
    """

    await update.message.reply_markdown(response)

    trade = {
        "capital": capital,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lot": lot,
        "risk": risk_amount,
        "reward": reward_amount,
        "risk_percent": risk_percent,
        "rr_ratio": rr_ratio,
        "symbol": context.args[0].upper() if context.args else "UNKNOWN",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    user_id = str(update.effective_user.id)
    if user_id in user_sheets:
        try:
            sheet = gc.open_by_key(user_sheets[user_id]).sheet1
            if len(sheet.get_all_records()) == 0:
                sheet.append_row(["Symbol", "Entry", "SL", "TP", "Lot", "Risk", "Reward", "RR Ratio", "Risk %", "Date"])
            sheet.append_row([
                trade["symbol"], trade["entry"], trade["sl"], trade["tp"],
                trade["lot"], trade["risk"], trade["reward"],
                f"1:{trade['rr_ratio']:.2f}", trade["risk_percent"], trade["date"]
            ])
            await update.message.reply_text("📄 Trade saved to your Google Sheet.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not write to Google Sheet: {e}")
    else:
        trade_journal.append(trade)
        await update.message.reply_text("📝 Trade logged in local journal. Use /linksheet to link Google Sheets.")

# /linksheet
async def linksheet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Provide your Google Sheet ID:\n/linksheet SHEET_ID")
        return

    user_id = str(update.effective_user.id)
    sheet_id = context.args[0]
    try:
        gc.open_by_key(sheet_id)
        user_sheets[user_id] = sheet_id
        await update.message.reply_text("✅ Google Sheet linked successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to access sheet: {e}")

# /sheethelp
async def sheethelp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = """
📘 *How to Get Your Google Sheet ID*:

1. Open your Google Sheet in a browser.
2. Look at the URL. You'll see something like:

`https://docs.google.com/spreadsheets/d/1ABCD123XYZ456efGHi789jkLmnopQRsTuVw/edit#gid=0`

3. Copy the long string between `/d/` and `/edit`:
👉 `1ABCD123XYZ456efGHi789jkLmnopQRsTuVw`

That is your **Sheet ID**.

🛡️ *IMPORTANT*: You must also share the sheet with the bot to allow it to edit.

👉 Go to the sheet > Click `Share` > Add this email:

`trading-bot-writer@ai-trade-assistant-sheets.iam.gserviceaccount.com`

Then use the `/linksheet` command like this:
`/linksheet 1ABCD123XYZ456efGHi789jkLmnopQRsTuVw`
    """
    await update.message.reply_markdown(help_msg)

# /remind
async def remind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.replace("/remind", "").strip()
    match = re.search(r"in (\d+)([hm]) to (.+)", msg, re.IGNORECASE)

    if not match:
        await update.message.reply_text("❌ Invalid format. Try:\n/remind me in 2h to check GBPUSD")
        return

    value, unit, reason = match.groups()
    seconds = int(value) * (3600 if unit.lower() == 'h' else 60)

    await update.message.reply_text(f"⏰ Reminder set! I’ll remind you in {value}{unit} to {reason}.")
    await asyncio.sleep(seconds)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📌 Reminder: {reason}") 

# /start handler 
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
👋 *Welcome to Lock-In Pal Bot* — your smart forex trade assistant powered by AI.

Here’s what I can help you do:
📊 Calculate trade risk & reward with `/riskcalc`  
⏰ Set trade reminders using `/remind`  
📝 Log and manage your trades with `/journal`, `/edittrade`, `/deletetrade`  
📄 Save entries to your *Google Sheet* via `/linksheet`  
📌 Export your logs with `/export`  
🧠 Stay in control of every move you make.

🔗 *First time here?* Start by linking your sheet:  
Use `/sheethelp` to learn how to get your Sheet ID,  
then `/linksheet SHEET_ID` to connect.

🌍 *Need a trusted broker?*  
We recommend [Exness](https://one.exnesstrack.org/a/c_ctqfjsjmem?platform=mobile) for tighter spreads & instant trade execution.

    """
    await update.message.reply_markdown(welcome_text)

# /journal
async def journal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    filtered = trade_journal

    if args:
        if args[0].lower() == "symbol" and len(args) > 1:
            filtered = [t for t in trade_journal if t["symbol"] == args[1].upper()]
        elif args[0].lower() == "date" and len(args) > 1:
            filtered = [t for t in trade_journal if t["date"].startswith(args[1])]

    if not filtered:
        await update.message.reply_text("📭 No matching trades found.")
        return

    response = "📓 *Filtered Trade Journal*:\n"
    for i, trade in enumerate(filtered, 1):
        response += (
            f"\n{i}. {trade['symbol']} | Entry: {trade['entry']} | SL: {trade['sl']} "
            f"| TP: {trade['tp']} | RR: 1:{trade['rr_ratio']:.2f} | {trade['date']}"
        )

    await update.message.reply_markdown(response)

# /export
async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    filtered = trade_journal

    if args:
        if args[0].lower() == "symbol" and len(args) > 1:
            filtered = [t for t in trade_journal if t["symbol"] == args[1].upper()]
        elif args[0].lower() == "date" and len(args) > 1:
            filtered = [t for t in trade_journal if t["date"].startswith(args[1])]

    if not filtered:
        await update.message.reply_text("📭 No matching trades to export.")
        return

    filename = "filtered_trade_export.csv"
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Symbol", "Entry", "SL", "TP", "RR Ratio", "Date"])
        for trade in filtered:
            writer.writerow([
                trade["symbol"], trade["entry"], trade["sl"], trade["tp"],
                f"1:{trade['rr_ratio']:.2f}", trade["date"]
            ])

    await update.message.reply_document(document=InputFile(filename), filename=filename)
    os.remove(filename)

# Feedback Handler 
async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = ' '.join(context.args)
    if not msg:
        await update.message.reply_text("✍️ Use /feedback followed by your message.")
        return
    admin_id = 1095821604
    await context.bot.send_message(chat_id=admin_id, text=f"📩 Feedback from {update.effective_user.username}:\n{msg}")
    await update.message.reply_text("✅ Thanks! We’ve received your feedback.")

# /edittrade
async def edittrade_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage:\n/edittrade [index] field:value ...")
        return

    try:
        index = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("❌ Invalid index.")
        return

    updates = dict(pair.split(":") for pair in context.args[1:] if ":" in pair)
    user_id = str(update.effective_user.id)

    if user_id in user_sheets:
        try:
            sheet = gc.open_by_key(user_sheets[user_id]).sheet1
            rows = sheet.get_all_records()
            if index < 0 or index >= len(rows):
                await update.message.reply_text("❌ Trade index out of range.")
                return
            trade = rows[index]
            for key in updates:
                if key.lower() in trade:
                    trade[key] = updates[key]
            values = list(trade.values())
            sheet.delete_rows(index + 2)
            sheet.insert_row(values, index + 2)
            await update.message.reply_text("✅ Trade updated in your Google Sheet.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not update Google Sheet: {e}")
    else:
        if index < 0 or index >= len(trade_journal):
            await update.message.reply_text("❌ Trade index out of range.")
            return
        trade = trade_journal[index]
        for k, v in updates.items():
            if k in trade:
                trade[k] = float(v) if k in ["entry", "sl", "tp", "lot"] else v
        await update.message.reply_text("✅ Trade updated in local journal.") 

# /privacy command
async def privacy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    policy = (
        "🔐 *Privacy Policy*\n\n"
        "This bot is designed to assist traders with risk management, journaling, trade reminders, and more.\n\n"
        "We do not collect or store personal information.\n"
        "Trade data is either:\n"
        "• stored temporarily in-memory (for unlinked users), or\n"
        "• saved directly to your linked Google Sheet — controlled solely by you.\n\n"
        "Your Google Sheet access is managed securely and only used to append your trade entries. "
        "You can revoke access anytime by unlinking the sheet or removing access to the bot's service account.\n\n"
        "📧 Developer Contact: oodilesr@gmail.com\n"
        "Telegram: @Fxxvinval"
    )
    await update.message.reply_markdown(policy)

# /deletetrade
async def deletetrade_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage:\n/deletetrade [index]")
        return

    try:
        index = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("❌ Invalid index.")
        return

    user_id = str(update.effective_user.id)

    if user_id in user_sheets:
        try:
            sheet = gc.open_by_key(user_sheets[user_id]).sheet1
            rows = sheet.get_all_records()
            if index < 0 or index >= len(rows):
                await update.message.reply_text("❌ Invalid trade index.")
                return
            sheet.delete_rows(index + 2)
            await update.message.reply_text("🗑️ Trade deleted from your Google Sheet.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not delete from Google Sheet: {e}")
    else:
        if index < 0 or index >= len(trade_journal):
            await update.message.reply_text("❌ Invalid trade index.")
            return
        deleted = trade_journal.pop(index)
        await update.message.reply_text(f"🗑️ Deleted trade: {deleted['symbol']} @ {deleted['date']}")

# Set up bot
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

# Run
async def main():
    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError as e:
        if "This Application is already running!" in str(e):
            print("⚠️ Bot already running.")
        else:
            raise
