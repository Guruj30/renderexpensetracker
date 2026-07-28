import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

load_dotenv()

# CRITICAL: We only pull the token. No default user IDs allowed!
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DB_PATH = 'finance.db'

# Live in-memory dictionary tracking individual user states privately
# Structure: { chat_id: {"authenticated": True, "user_id": X, "username": "..."} }
USER_SESSIONS = {}

def get_main_keyboard():
    """Generates the private dashboard button console layout."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Available Balance", callback_data="check_balance"),
        ],
        [
            InlineKeyboardButton("📈 Total Income", callback_data="total_income"),
            InlineKeyboardButton("📉 Total Expense", callback_data="total_expense"),
        ],
        [
            InlineKeyboardButton("🥇 Top Income Cat", callback_data="top_inc_cat"),
            InlineKeyboardButton("🥈 Top Expense Cat", callback_data="top_exp_cat"),
        ],
        [
            InlineKeyboardButton("📊 Weekly Summary", callback_data="weekly_summary"),
            InlineKeyboardButton("📅 Monthly Summary", callback_data="monthly_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def generate_text_chart(data_dict, title):
    """Generates a pure text bar chart using block indicators."""
    if not data_dict:
        return f"📊 *{title}*\nNo data records available."
        
    max_val = max(data_dict.values()) if max(data_dict.values()) > 0 else 1
    chart_lines = [f"📊 *{title}*:\n"]
    
    for key, val in data_dict.items():
        bar_count = int((val / max_val) * 8)
        blocks = "█" * bar_count + "░" * (8 - bar_count)
        chart_lines.append(f"`{key[:10]:<10}` | {blocks} | ₹{val:,.2f}")
        
    return "\n".join(chart_lines)


def parse_combined_finance_message(text):
    """Parses incoming transaction text strings."""
    text_lines = [line.strip() for line in text.replace(',', '\n').split('\n') if line.strip()]
    extracted_records = []

    for line in text_lines:
        line_lower = line.lower()
        amount_match = re.search(r'\b\d+(?:\.\d{1,2})?\b', line)
        if not amount_match:
            continue
        amount = float(amount_match.group())

        is_income = any(w in line_lower for w in ['income', 'geted', 'got', 'received', 'earned', 'credited', 'deposit'])
        tx_type = 'income' if is_income else 'expense'

        note_text = ""
        note_match = re.search(r'\b(note|desc|ref|details)\b\s*[:\-]?\s*(.*)', line, re.IGNORECASE)
        if note_match:
            note_text = note_match.group(2).strip()
            line_lower = line_lower.replace(note_match.group(0).lower(), "")

        clean_text = re.sub(r'\b\d+(?:\.\d{1,2})?\b', '', line_lower)
        words = [w for w in clean_text.split() if w not in [
            'amount', 'spent', 'spended', 'on', 'income', 'geted', 'got', 'received', 
            'for', 'a', 'an', 'the', 'expenditure', 'outcome', 'rupees', 'rs', 'check', 'balance'
        ]]
        
        category = " ".join(words).strip().title()
        if not category:
            category = "General"

        extracted_records.append({
            "type": tx_type,
            "amount": amount,
            "category": category,
            "note": note_text if note_text else "Logged via Telegram Multi-Agent"
        })

    return extracted_records


def handle_button_clicks(update: Update, context: CallbackContext):
    """Processes button clicks securely based on the user's isolated chat_id."""
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    
    # 🔒 BLOCK ACCESS IF NOT LOGGED IN
    if chat_id not in USER_SESSIONS or not USER_SESSIONS[chat_id].get("authenticated"):
        query.message.reply_text("🔒 Your session expired or is unauthorized. Please log in using: `username password`")
        return
        
    # Dynamically extract the specific logged-in user's web database ID
    user_id = USER_SESSIONS[chat_id]["user_id"]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if query.data == "check_balance":
        cursor.execute("SELECT type, amount FROM transactions WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        inc = sum(r[1] for r in rows if r[0] == 'income')
        exp = sum(r[1] for r in rows if r[0] == 'expense')
        bal = inc - exp
        query.message.reply_text(f"💰 *Available Balance:* ₹{bal:,.2f}\n📦 (Income: ₹{inc:,.2f} | Expense: ₹{exp:,.2f})", parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "total_income":
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income'", (user_id,))
        val = cursor.fetchone()[0] or 0.0
        query.message.reply_text(f"📈 *Cumulative Income:* ₹{val:,.2f}", parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "total_expense":
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense'", (user_id,))
        val = cursor.fetchone()[0] or 0.0
        query.message.reply_text(f"📉 *Cumulative Expenses:* ₹{val:,.2f}", parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "top_inc_cat":
        cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income' GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        msg = f"🥇 *Top Income Stream:* {row[0]} (₹{row[1]:,.2f})" if row else "🥇 No income categories recorded yet."
        query.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "top_exp_cat":
        cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        msg = f"🥈 *Top Drain Category:* {row[0]} (₹{row[1]:,.2f})" if row else "🥈 No expense categories recorded yet."
        query.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "weekly_summary":
        seven_days_ago = (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute("SELECT date, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND date >= ? GROUP BY date ORDER BY date ASC", (user_id, seven_days_ago))
        days_data = {r[0][-5:]: r[1] for r in cursor.fetchall()}
        chart = generate_text_chart(days_data, "Weekly Expense Breakdown (Past 7 Days)")
        query.message.reply_text(chart, parse_mode='Markdown', reply_markup=get_main_keyboard())

    elif query.data == "monthly_summary":
        cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' GROUP BY category ORDER BY SUM(amount) DESC", (user_id,))
        cat_data = {r[0]: r[1] for r in cursor.fetchall()}
        chart = generate_text_chart(cat_data, "Monthly Category Consumption Share")
        query.message.reply_text(chart, parse_mode='Markdown', reply_markup=get_main_keyboard())

    conn.close()


def handle_telegram_message(update: Update, context: CallbackContext):
    """Processes message inputs privately per user session profile."""
    chat_id = update.message.chat_id
    user_message = update.message.text.strip()
    
    # 🔐 FORCE STEP: AUTHENTICATE INCOMING CHAT ID FIRST
    if chat_id not in USER_SESSIONS or not USER_SESSIONS[chat_id].get("authenticated"):
        credentials = user_message.split()
        if len(credentials) == 2:
            input_user, input_pass = credentials[0], credentials[1]
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, password FROM users WHERE username = ?", (input_user,))
            user_record = cursor.fetchone()
            conn.close()

            if user_record and check_password_hash(user_record[1], input_pass):
                # Save data to this user's isolated session space
                USER_SESSIONS[chat_id] = {"authenticated": True, "user_id": user_record[0], "username": input_user}
                update.message.reply_text(
                    f"🔓 **Access Granted!** Connected to account: **{input_user}**.\nUse the dashboard console options below:",
                    reply_markup=get_main_keyboard()
                )
                return
            else:
                update.message.reply_text("❌ Authentication Failed! Invalid credentials.")
                return
        else:
            update.message.reply_text("🔒 *Security Authorization Required.*\nReply directly with your web details: `username password`")
            return

    # 🛒 TRANSACTION HANDLING (Only runs if authenticated successfully)
    active_profile = USER_SESSIONS[chat_id]
    target_user_id = active_profile["user_id"] # Safe dynamic web user mapping
    
    parsed_entries = parse_combined_finance_message(user_message)

    if not parsed_entries:
        update.message.reply_text("❓ Unknown request. Type an expense/income prompt or use the menu items below.", reply_markup=get_main_keyboard())
        return

    try:
        today_str = date.today().strftime('%Y-%m-%d')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        success_details = []
        for entry in parsed_entries:
            cursor.execute(
                "INSERT INTO transactions (user_id, type, amount, category, date, note) VALUES (?, ?, ?, ?, ?, ?)",
                (target_user_id, entry['type'], entry['amount'], entry['category'], today_str, entry['note'])
            )
            success_details.append(f"🔹 *{entry['type'].upper()}*: ₹{entry['amount']} ➔ {entry['category']}")

        conn.commit()
        conn.close()

        update.message.reply_text(
            f"✅ **Saved to your personal dashboard!**\n" + "\n".join(success_details),
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        update.message.reply_text(f"⚠️ Error updating data: {str(e)}", reply_markup=get_main_keyboard())


def start_telegram_bot():
    if not TELEGRAM_TOKEN:
        print("⚠️ Warning: Bot token absent.")
        return
        
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CallbackQueryHandler(handle_button_clicks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_telegram_message))
    
    print("🤖 Multi-User Isolated Control Agent online...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    start_telegram_bot()