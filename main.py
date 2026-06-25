import sqlite3
import time
import requests
import re
import threading
from flask import Flask

app = Flask(__name__)

# ==========================================
# 🔑 بيانات البوت والآيديات
# ==========================================
BOT_TOKEN = "8889630212:AAHc8EyGdhiJDq6uIfgDYlIX_-A7TrCyS9I"
ALLOWED_USERS = {7906637031, 6199220525, 8520205949, 8877182287}

# ==========================================
# 🌐 سيرفر الـ 24 ساعة
# ==========================================
@app.route('/')
def home():
    return "VIP System is Running 24/7!"

def run_server():
    app.run(host="0.0.0.0", port=8000)

# ==========================================
# 💾 قواعد البيانات 
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

# ==========================================
# 🛠️ الدوال المساعدة (Helpers)
# ==========================================
def tg_request(method, payload):
    def send_it():
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass
    threading.Thread(target=send_it, daemon=True).start()

def get_time_left(save_time, timer_alert):
    if not timer_alert or timer_alert <= 0: return "بدون تايمر ⚪"
    diff = (save_time + (timer_alert * 60)) - time.time()
    if diff <= 0: return "انتهى الوقت 🔴"
    return f"⏳ {int(diff // 60)} دقيقة"

def send_backup(chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open("bot_data.db", "rb") as file:
            requests.post(url, data={"chat_id": chat_id, "caption": "💾 **نسختك الاحتياطية من البيانات.**\nاحتفظ بهذا الملف للآمان.", "parse_mode": "Markdown"}, files={"document": file})
    except Exception:
        tg_request("sendMessage", {"chat_id": chat_id, "text": "❌ لا توجد بيانات مسجلة حتى الآن لحفظها."})

# ==========================================
# 🎛️ واجهة لوحة التحكم (الزراير المربعة)
# ==========================================
def send_main_menu(chat_id, message_id=None):
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✍️ إضافة بطاقة", "callback_data": "menu_add"},
                {"text": "📋 عرض البطاقات", "callback_data": "menu_view"}
            ],
            [
                {"text": "🔍 بحث سريع", "callback_data": "menu_search"},
                {"text": "✏️ تعديل بطاقة", "callback_data": "menu_edit"}
            ],
            [
                {"text": "🗑️ حذف بطاقة", "callback_data": "menu_delete"},
                {"text": "💾 نسخة احتياطية", "callback_data": "menu_backup"}
            ]
        ]
    }
    msg_text = "⚡️ **لوحة تحكم النظام (VIP Dashboard)** ⚡️\n\nاختر الإجراء المطلوب من الأزرار أدناه:"
    
    if message_id:
        tg_request("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard})
    else:
        tg_request("sendMessage", {"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard})

# ==========================================
# ⏱️ نظام الفحص الآلي (كل 5 ثواني)
# ==========================================
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
                    msg = f"🚨 **إشعار الدفعة القادمة!** 🚨\n\n💳 البطاقة: `[ {last4} ]`\n💰 الرصيد المتاح: **${balance}**\n🔄 العداد المتبقي: `{counter}`\n\nقم بالدخول للوحة التحكم لتحديث البيانات."
                    tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
                    c.execute("UPDATE cards SET notified='YES' WHERE id=?", (card_id,))
            conn.commit()
    except Exception:
        pass

def auto_check_loop():
    while True:
        check_timers()
        time.sleep(5)

# ==========================================
# 🚀 معالجة المدخلات (الرسائل والزراير)
# ==========================================
def process_update(update):
    chat_id = None
    if "message" in update and "chat" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
    elif "callback_query" in update:
        chat_id = update["callback_query"]["message"]["chat"]["id"]

    if chat_id and chat_id not in ALLOWED_USERS:
        return

    # ----------------------------------
    # 📝 أولاً: معالجة الرسائل النصية
    # ----------------------------------
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"]
        
        # أمر البداية
        if text in ["/start", "start", "/main"]:
            send_main_menu(chat_id)
            return

        # البحث السريع (لو كتب 4 أرقام)
        if re.match(r'^\d{4}$', text.strip()):
            search_last4 = text.strip()
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM cards WHERE card_number LIKE ?", (f"%{search_last4}",))
                rows = c.fetchall()
                if rows:
                    for row in rows:
                        last4 = row[2][-4:]
                        msg = f"🔍 **نتيجة البحث:**\n\n💳 الكارت: `[ {last4} ]`\n💰 الرصيد: `${row[3]}`\n🔄 العداد: `{row[4]}`\n⏳ الوقت: {get_time_left(row[1], row[6])}"
                        keyboard = {"inline_keyboard": [[{"text": "✏️ تعديل", "callback_data": f"edit_prompt_{last4}"}], [{"text": "🔙 القائمة", "callback_data": "back_to_main"}]]}
                        tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})
                else:
                    tg_request("sendMessage", {"chat_id": chat_id, "text": f"❌ لم يتم العثور على كارت ينتهي بـ {search_last4}"})
            return

        # تعديل يدوي
        if text.startswith("تعديل |"):
            try:
                parts = text.split("|")
                last4 = parts[1].strip()
                new_balance = float(parts[2].strip())
                new_counter = int(parts[3].strip())
                new_timer = int(parts[4].strip())

                with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                    c = conn.cursor()
                    c.execute("UPDATE cards SET balance=?, counter=?, timer_alert=?, notified='NO', save_time=? WHERE card_number LIKE ?", 
                              (new_balance, new_counter, new_timer, time.time(), f"%{last4}"))
                    if c.rowcount > 0:
                        tg_request("sendMessage", {"chat_id": chat_id, "text": f"✅ **تم التحديث!**\nالكارت `[ {last4} ]` تم حفظ بياناته الجديدة.", "parse_mode": "Markdown"})
                        send_main_menu(chat_id)
                    else:
                        tg_request("sendMessage", {"chat_id": chat_id, "text": "❌ خطأ: الكارت غير موجود."})
                    conn.commit()
            except Exception:
                tg_request("sendMessage", {"chat_id": chat_id, "text": "❌ التنسيق غير صحيح."})
            return

        # التقاط الفيزا التلقائي
        if "Balance:" in text or "Purchase Successful" in text:
            card_match = re.search(r'\b(\d{16})\b', text)
            balance_match = re.search(r'Balance:\s*\$?\s*([\d\.]+)', text)
            if card_match and balance_match:
                card_num = card_match.group(1)
                balance = balance_match.group(1)
                last4 = card_num[-4:]
                keyboard = {"inline_keyboard": [
                    [{"text": "1", "callback_data": f"st2_{card_num}_{balance}_1"}, {"text": "2", "callback_data": f"st2_{card_num}_{balance}_2"}, {"text": "3", "callback_data": f"st2_{card_num}_{balance}_3"}],
                    [{"text": "4", "callback_data": f"st2_{card_num}_{balance}_4"}, {"text": "5", "callback_data": f"st2_{card_num}_{balance}_5"}],
                    [{"text": "🔙 إلغاء", "callback_data": "back_to_main"}]
                ]}
                msg = f"✅ **فيزا جديدة!**\n💳 `[ **** {last4} ]`\n💰 الرصيد: `${balance}`\n\n👇 **اختر العداد:**"
                tg_request("sendMessage", {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})
                return

        # إضافة يدوية كاملة
        elif "|" in text and len(text.split("|")) == 5 and not text.startswith("تعديل"):
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
                tg_request("sendMessage", {"chat_id": chat_id, "text": "✅ **تم حفظ البطاقة في النظام.**", "parse_mode": "Markdown"})
                send_main_menu(chat_id)
            except ValueError:
                pass
        else:
            send_main_menu(chat_id)

    # ----------------------------------
    # 🖱️ ثانياً: معالجة الأزرار
    # ----------------------------------
    elif "callback_query" in update:
        cb = update["callback_query"]
        callback_id = cb["id"]
        data = cb["data"]
        msg_id = cb["message"]["message_id"]

        tg_request("answerCallbackQuery", {"callback_query_id": callback_id})

        # زر الرجوع للقائمة
        if data == "back_to_main":
            send_main_menu(chat_id, msg_id)

        # أوامر القائمة الرئيسية المربعة
        elif data == "menu_add":
            msg = "✍️ **لإضافة بطاقة يدوياً:**\nأرسل رسالة بهذا التنسيق:\n`رقم البطاقة | الرصيد | العداد | المدفوع | التايمر`\n\n*(أو قم بعمل إعادة توجيه لرسالة الدفع وسيتم التقاطها آلياً)*"
            keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data == "menu_search":
            msg = "🔍 **البحث السريع:**\nالآن قم بإرسال **آخر 4 أرقام** من البطاقة في الشات للبحث عنها.\n*(مثال: أرسل `1234`)*"
            keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data == "menu_edit":
            msg = "✏️ **تعديل بطاقة موجودة:**\nلتعديل الرصيد أو العداد أو الوقت، انسخ التنسيق التالي واملأه:\n\n`تعديل | آخر_4_أرقام | الرصيد | العداد | التايمر`\n\n*(مثال: تعديل | 1234 | 40.5 | 2 | 15)*"
            keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data == "menu_backup":
            tg_request("deleteMessage", {"chat_id": chat_id, "message_id": msg_id})
            send_backup(chat_id)
            send_main_menu(chat_id)

        elif data == "menu_view":
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM cards ORDER BY id DESC LIMIT 10")
                rows = c.fetchall()

            if not rows:
                keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
                tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "📭 النظام فارغ، لا توجد بطاقات محفوظة.", "reply_markup": keyboard})
                return

            keyboard = []
            for row in rows:
                last4 = row[2][-4:] if len(row[2]) >= 4 else row[2]
                btn_text = f"💳 [ {last4} ] | ${row[3]} | {get_time_left(row[1], row[6])}"
                keyboard.append([{"text": btn_text, "callback_data": f"card_{row[0]}"}])
            keyboard.append([{"text": "🔙 رجوع للقائمة الرئيسية", "callback_data": "back_to_main"}])
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "📋 **قائمة البطاقات الحالية:**\n*(اضغط على الكارت للتفاصيل)*", "reply_markup": {"inline_keyboard": keyboard}, "parse_mode": "Markdown"})

        elif data == "menu_delete":
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT id, card_number FROM cards ORDER BY id DESC LIMIT 10")
                rows = c.fetchall()

            if not rows:
                keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
                tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "⚠️ لا توجد بطاقات لمسحها.", "reply_markup": keyboard})
                return

            keyboard = []
            for row in rows:
                last4 = row[1][-4:] if len(row[1]) >= 4 else row[1]
                keyboard.append([{"text": f"❌ حذف: [ {last4} ]", "callback_data": f"del_{row[0]}"}])
            keyboard.append([{"text": "🔙 إلغاء والرجوع", "callback_data": "back_to_main"}])
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "🗑️ **اختر البطاقة لنهائياً من النظام:**", "reply_markup": {"inline_keyboard": keyboard}, "parse_mode": "Markdown"})

        # تفاصيل الكارت
        elif data.startswith("card_"):
            card_id = data.split("_")[1]
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM cards WHERE id=?", (card_id,))
                row = c.fetchone()
            if row:
                last4 = row[2][-4:] if len(row[2]) >= 4 else row[2]
                msg = f"💎 **تفاصيل البطاقة:**\n\n🔢 رقم النهاية: `[ {last4} ]`\n💰 الرصيد المتاح: `${row[3]}`\n🔄 العداد: `{row[4]}`\n⏳ الوقت المتبقي: {get_time_left(row[1], row[6])}"
                keyboard = {"inline_keyboard": [
                    [{"text": "✏️ تعديل سريع", "callback_data": f"edit_prompt_{last4}"}, {"text": "❌ حذف الكارت", "callback_data": f"del_{card_id}"}],
                    [{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]
                ]}
                tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("edit_prompt_"):
            last4 = data.split("_")[2]
            msg = f"✏️ **تعديل الكارت `[ {last4} ]`**\n\nارسل التعديل الان كالتالي:\n`تعديل | {last4} | الرصيد | العداد | التايمر`"
            keyboard = {"inline_keyboard": [[{"text": "🔙 إلغاء", "callback_data": "back_to_main"}]]}
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("del_"):
            card_id = data.split("_")[1]
            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM cards WHERE id=?", (card_id,))
                conn.commit()
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "✅ **تم الحذف بنجاح.**", "parse_mode": "Markdown"})
            send_main_menu(chat_id)

        # استكمال إضافة كارت جديد
        elif data.startswith("st2_"):
            parts = data.split("_")
            card_num, balance, counter = parts[1], parts[2], parts[3]
            keyboard = {"inline_keyboard": [
                [{"text": "1", "callback_data": f"st3_{card_num}_{balance}_{counter}_1"}, {"text": "3", "callback_data": f"st3_{card_num}_{balance}_{counter}_3"}],
                [{"text": "5", "callback_data": f"st3_{card_num}_{balance}_{counter}_5"}, {"text": "10", "callback_data": f"st3_{card_num}_{balance}_{counter}_10"}],
                [{"text": "🔙 إلغاء", "callback_data": "back_to_main"}]
            ]}
            msg = f"💳 `[ **** {card_num[-4:]} ]` | 💰 `${balance}`\n🔢 العداد المختار: `{counter}`\n\n👇 **المدفوع الآن:**"
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("st3_"):
            parts = data.split("_")
            card_num, balance, counter, paid = parts[1], parts[2], parts[3], parts[4]
            keyboard = {"inline_keyboard": [
                [{"text": "1 دقيقة", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_1"}, {"text": "2 دقيقة", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_2"}],
                [{"text": "3 دقيقة", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_3"}, {"text": "5 دقيقة", "callback_data": f"sav_{card_num}_{balance}_{counter}_{paid}_5"}],
                [{"text": "🔙 إلغاء", "callback_data": "back_to_main"}]
            ]}
            msg = f"💳 `[ **** {card_num[-4:]} ]` | 💰 `${balance}`\n🔢 العداد: `{counter}` | 💵 خُصم: `${paid}`\n\n👇 **اختر التايمر:**"
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

        elif data.startswith("sav_"):
            parts = data.split("_")
            card_num = parts[1]
            original_balance, paid_now = float(parts[2]), float(parts[4])
            original_counter, timer_alert = int(parts[3]), int(parts[5])

            new_balance = max(0.0, original_balance - paid_now)
            new_counter = max(0, original_counter - 1)

            with sqlite3.connect("bot_data.db", check_same_thread=False, timeout=20) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO cards (save_time, card_number, balance, counter, paid_now, timer_alert, chat_id, notified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (time.time(), card_num, new_balance, new_counter, paid_now, timer_alert, str(chat_id), "NO"))
                conn.commit()

            msg = f"✅ **تم حفظ البطاقة بنجاح وتشغيل التايمر!**\n💰 الرصيد المتبقي: `${new_balance}`\n🔄 العداد المتبقي: `{new_counter}`"
            keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]]}
            tg_request("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": msg, "parse_mode": "Markdown", "reply_markup": keyboard})

# ==========================================
# 📡 حلقة الاتصال المباشر 
# ==========================================
def start_polling():
    offset = 0
    print("✅ System Online! No Webhooks needed.")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            res = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=40).json()
            if "result" in res:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    process_update(update)
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except: pass
    
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=auto_check_loop, daemon=True).start()
    
    start_polling()
