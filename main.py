import sqlite3
import time
import requests
import re
import threading
from flask import Flask

app = Flask(__name__)

# بيانات البوت بتاعك
BOT_TOKEN = "8889630212:AAHc8EyGdhiJDq6uIfgDYlIX_-A7TrCyS9I"

# 🛑 حط هنا الآيدي (ID) بتاعك
ALLOWED_USERS = {7906637031, 6199220525, 8520205949, 8877182287}

# ==========================================
# 🌐 سيرفر الـ 24 ساعة (عشان Replit ميفصلش)
# ==========================================
@app.route('/')
def home():
    return "Bot is Running 24/7 (Polling Mode)!"

def run_server():
    # بنشغل السيرفر على بورت 8000 عشان نتفادى أي تعليق
    app.run(host="0.0.0.0", port=8000)

# ==========================================
# 💾 قواعد البيانات والإشعارات
# ==========================================
def init_db():
    with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS cards
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, save_time REAL, card_number TEXT,
                      balance REAL, counter INTEGER, paid_now REAL, timer_alert INTEGER,
                      chat_id TEXT, notified TEXT)''')
        conn.commit()

init_db()

def tg_request(method, payload):
    def send_it():
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass
    threading.Thread(target=send_it, daemon=True).start()

def send_main_menu(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "✍️ Add Card (Via Chat)", "callback_data": "add_via_chat"}],
            [{"text": "🚀 Launch/Start", "callback_data": "launch_start"}],
            [{"text": "📋 View Cards", "callback_data": "view_cards"}],
            [{"text": "🗑️ Delete Specific Card", "callback_data": "delete_card"}]
        ]
    }
    tg_request("sendMessage", {"chat_id": chat_id, "text": "⚡️ Card Management System ⚡\nاختر من القائمة:", "reply_markup": keyboard})

def get_time_left(save_time, timer_alert):
    if not timer_alert or timer_alert <= 0: return "No Timer"
    diff = (save_time + (timer_alert * 60)) - time.time()
    if diff <= 0: return "Expired 🔴"
    return f"⏳ {int(diff // 60)} Min"

def check_timers():
    now = time.time()
    try:
        with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM cards WHERE notified='NO' AND timer_alert > 0")
            cards = c.fetchall()
            for row in cards:
                card_id, save_time, card_num, balance, counter, paid_now, timer_alert, chat_id, notified = row
                if now >= save_time + (timer_alert * 60):
                    last4 = card_num[-4:] if len(card_num) >= 4 else card_num
                    msg = f"🚨 **حان موعد الدفعة الثانية!** 🚨\n\n💳 البطاقة: `[ {last4} ]`\n💰 الرصيد المتبقي: **${balance}**\n🔄 العداد المتبقي: `{counter}`"
                    tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
                    c.execute("UPDATE cards SET notified='YES' WHERE id=?", (card_id,))
            conn.commit()
    except Exception as e:
        pass

def auto_check_loop():
    while True:
        check_timers()
        time.sleep(60)

# ==========================================
# 🚀 معالجة الرسائل
# ==========================================
def process_update(update):
    chat_id = None
    if "message" in update and "chat" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
    elif "callback_query" in update:
        chat_id = update["callback_query"]["message"]["chat"]["id"]

    if chat_id and chat_id not in ALLOWED_USERS:
        return

    # معالجة الرسائل
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"]
        
        if text in ["/start", "start"]:
            send_main_menu(chat_id)
            return

        if "Balance:" in text or "Purchase Successful" in text:
            card_match = re.search(r'\b(\d{16})\b', text)
            balance_match = re.search(r'Balance:\s*\$?\s*([\d\.]+)', text)

            if card_match and balance_match:
                card_num = card_match.group(1)
                balance = balance_match.group(1)
                last4 = card_num[-4:]

                keyboard = {"inline_keyboard": [
                    [
                        {"text": "1", "callback_data": f"st2_{card_num}_{balance}_1"},
                        {"text": "2", "callback_data": f"st2_{card_num}_{balance}_2"},
                        {"text": "3", "callback_data": f"st2_{card_num}_{balance}_3"},
                        {"text": "4", "callback_data": f"st2_{card_num}_{balance}_4"},
                        {"text": "5", "callback_data": f"st2_{card_num}_{balance}_5"}
                    ]
                ]}
                msg = f"✅ **تم التقاط الفيزا بنجاح!**\n💳 الفيزا: `[ **** {last4} ]`\n💰 الرصيد المكتشف: `${balance}`\n\n👇 **اختر العداد (Counter):**"
                tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})
                return

        elif "|" in text and len(text.split("|")) == 5:
            try:
                parts = text.split("|")
                card_num = parts[0].strip()
                original_balance = float(parts[1].strip())
                original_counter = int(parts[2].strip())
                paid_now = float(parts[3].strip())
                timer_alert = int(parts[4].strip())

                new_balance = max(0.0, original_balance - paid_now)
                new_counter = max(0, original_counter - 1)

                with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO cards (save_time, card_number, balance, counter, paid_now, timer_alert, chat_id, notified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (time.time(), card_num, new_balance, new_counter, paid_now, timer_alert, str(chat_id), "NO"))
                    conn.commit()

                tg_request("sendMessage", {"chat_id": chat_id, "text": "✅ **تم حفظ البطاقة بنجاح!**", "parse_mode": "Markdown"})
                send_main_menu(chat_id)
            except ValueError:
                tg_request("sendMessage", {"chat_id": chat_id, "text": "❌ **حدث خطأ في الأرقام!**", "parse_mode": "Markdown"})
        else:
            send_main_menu(chat_id)

    # معالجة الزراير
    elif "callback_query" in update:
        cb = update["callback_query"]
        callback_id = cb["id"]
        data = cb["data"]
        msg_id = cb["message"]["message_id"]

        tg_request("answerCallbackQuery", {"callback_query_id": callback_id})

        if data.startswith("st2_"):
            parts = data.split("_")
            card_num = parts[1]
            balance = parts[2]
            counter = parts[3]

            keyboard = {"inline_keyboard": [
                [
                    {"text": "1", "callback_data": f"st3_{card_num}_{balance}_{counter}_1"},
                    {"text": "3", "callback_data": f"st3_{card_num}_{balance}_{counter}_3"},
                    {"text": "5", "callback_data": f"st3_{card_num}_{balance}_{counter}_5"},
                    {"text": "6", "callback_data": f"st3_{card_num}_{balance}_{counter}_6"}
                ],
                [
                    {"text": "7", "callback_data": f"st3_{card_num}_{balance}_{counter}_7"},
                    {"text": "10", "callback_data": f"st3_{card_num}_{balance}_{counter}_10"},
                    {"text": "20", "callback_data": f"st3_{card_num}_{balance}_{counter}_20"}
                ]
            ]}
            msg = f"💳 الفيزا: `[ **** {card_num[-4:]} ]` | 💰 الرصيد: `${balance}`\n🔢 العداد المختار: `{counter}`\n\n👇 **اختر المدفوع الآن (Paid Now):**"
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("st3_"):
            parts = data.split("_")
            card_num = parts[1]
            balance = parts[2]
            counter = parts[3]
            paid = parts[4]

            keyboard = {"inline_keyboard": [
                [
                    {"text": "1", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_1"},
                    {"text": "2", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_2"},
                    {"text": "3", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_3"},
                    {"text": "4", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_4"},
                    {"text": "5", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_5"}
                ]
            ]}
            msg = f"💳 الفيزا: `[ **** {card_num[-4:]} ]` | 💰 الرصيد: `${balance}`\n🔢 العداد: `{counter}` | 💵 المدفوع: `${paid}`\n\n👇 **اختر التايمر بالدقائق (Timer):**"
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("sav_"):
            parts = data.split("_")
            card_num = parts[1]
            original_balance = float(parts[2])
            original_counter = int(parts[3])
            paid_now = float(parts[4])
            timer_alert = int(parts[5])

            new_balance = max(0.0, original_balance - paid_now)
            new_counter = max(0, original_counter - 1)

            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO cards (save_time, card_number, balance, counter, paid_now, timer_alert, chat_id, notified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (time.time(), card_num, new_balance, new_counter, paid_now, timer_alert, str(chat_id), "NO"))
                conn.commit()

            msg = f"✅ **تم استكمال وحفظ البطاقة بنجاح!**\n💰 الرصيد المتبقي: `${new_balance}`\n🔄 العداد المتبقي: `{new_counter}`\n⏳ التايمر يعمل الآن في الخلفية، سيصلك إشعار فور الانتهاء!"
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown"})
            send_main_menu(chat_id)

        elif data == "launch_start":
            tg_request("sendMessage", {"chat_id": chat_id, "text": "✅ System launched successfully..."})
            send_main_menu(chat_id)

        elif data == "add_via_chat":
            msg = "يمكنك الآن عمل **إعادة توجيه (Forward)** لرسالة الشراء، أو إرسال البيانات يدوياً بالتنسيق:\n`رقم البطاقة | الرصيد | العداد | المدفوع | التايمر`"
            tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

        elif data == "view_cards":
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM cards ORDER BY id DESC LIMIT 10")
                rows = c.fetchall()

            if not rows:
                tg_request("sendMessage", {"chat_id": chat_id, "text": "No cards saved currently."})
                return

            keyboard = []
            for count, row in enumerate(rows):
                card_num = row[2]
                last4 = card_num[-4:] if len(card_num) >= 4 else card_num
                btn_text = f"{count + 1}. [ {last4} ] | ${row[3]} | {get_time_left(row[1], row[6])}"
                keyboard.append([{"text": btn_text, "callback_data": f"card_{row[0]}"}])

            tg_request("sendMessage", {"chat_id": chat_id, "text": "📋 Current Cards List:", "reply_markup": {"inline_keyboard": keyboard}})

        elif data == "delete_card":
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT id, card_number FROM cards ORDER BY id DESC LIMIT 10")
                rows = c.fetchall()

            if not rows:
                tg_request("sendMessage", {"chat_id": chat_id, "text": "⚠️ لا توجد بطاقات محفوظة حالياً لمسحها."})
                send_main_menu(chat_id)
                return

            keyboard = []
            for row in rows:
                card_num = row[1]
                last4 = card_num[-4:] if len(card_num) >= 4 else card_num
                btn_text = f"❌ مسح: [ {last4} ]"
                keyboard.append([{"text": btn_text, "callback_data": f"del_{row[0]}"}])

            keyboard.append([{"text": "🔙 رجوع", "callback_data": "launch_start"}])
            tg_request("sendMessage", {"chat_id": chat_id, "text": "🗑️ **اختر البطاقة التي تريد مسحها:**", "reply_markup": {"inline_keyboard": keyboard}, "parse_mode": "Markdown"})

        elif data.startswith("del_"):
            card_id = data.split("_")[1]
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM cards WHERE id=?", (card_id,))
                conn.commit()
            tg_request("sendMessage", {"chat_id": chat_id, "text": "✅ **تم مسح البطاقة بنجاح!**", "parse_mode": "Markdown"})
            send_main_menu(chat_id)

        elif data.startswith("card_"):
            card_id = data.split("_")[1]
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM cards WHERE id=?", (card_id,))
                row = c.fetchone()
            if row:
                card_num = row[2]
                last4 = card_num[-4:] if len(card_num) >= 4 else card_num
                msg = f"💳 **Card Details** 💳\n\n🔢 Card: `[ {last4} ]`\n💰 Balance: ${row[3]}\n🔄 Counter: {row[4]}\n💵 Paid: ${row[5]}\n⏳ Time Left: {get_time_left(row[1], row[6])}"
                tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

# ==========================================
# 📡 حلقة الاتصال المباشر (Polling)
# ==========================================
def start_polling():
    offset = 0
    print("✅ Bot is Running (Polling Mode)... No Webhooks or Links needed for Telegram!")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            res = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=40).json()

            if "result" in res:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    process_update(update)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    # 1. مسح الـ Webhook القديم عشان ميحصلش تعارض
    print("🔄 Cleaning old webhook...")
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except:
        pass
    
    # 2. تشغيل السيرفر الوهمي في الخلفية (عشان الـ 24 ساعة)
    threading.Thread(target=run_server, daemon=True).start()

    # 3. تشغيل فحص الإشعارات والتايمر في الخلفية
    threading.Thread(target=auto_check_loop, daemon=True).start()
    
    # 4. تشغيل البوت المباشر
    start_polling()
