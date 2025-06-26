
# 📈 AI Trade Assistant Telegram Bot

**AI Trade Assistant** is an intelligent Telegram bot built for **forex and financial traders**.  
It helps traders manage risk, log trades, calculate positions, and track performance — all directly inside Telegram.

---

## 🚀 Features

| Command | Description |
|--------|-------------|
| `/start` | View a welcome message and all available features |
| `/riskcalc` | Step-by-step trade risk calculator (entry, SL, account, risk %, optional TP) |
| `/logtrade` | Log a trade manually by specifying parameters |
| `/marktrade` | Mark the result of a trade as `win`, `loss`, or `breakeven` |
| `/weeklysummary` | Get a performance summary of all trades for the current week |
| `/journal` | View your locally saved trades |
| `/linksheet` | Link your bot to your personal Google Sheet for auto journaling |
| `/sheethelp` | Get instructions on how to retrieve your Google Sheet ID |
| `/deletetrade` | Delete a specific trade from your journal (by index) |
| `/edittrade` | Edit a logged trade by index |
| `/remind` | Set a reminder message in the future |
| `/help` | Get usage help and contact support |

---

## 📌 Setup Instructions

### 🔐 Requirements
- Python 3.9+
- A Telegram bot token (get from [@BotFather](https://t.me/BotFather))
- A Google Service Account + Google Sheet (optional for journaling)

### 📦 Installation

```bash
git clone https://github.com/your-username/ai-trade-assistant-bot.git
cd ai-trade-assistant-bot
pip install -r requirements.txt
```

### ⚙️ Configure

- Rename `.env.example` to `.env` and add your `BOT_TOKEN` and `GOOGLE_CREDENTIALS_JSON`
- Link your Google Sheet using the `/linksheet` command

---

## 🧠 How It Works

- The bot walks you through trade input step-by-step via chat
- Automatically calculates lot size based on SL and risk %
- Optionally evaluates RR ratio and gives trade quality advice
- Saves all trades locally or to your Google Sheet
- Weekly summaries are generated based on marked trade outcomes

---

## 📄 License
MIT

---

