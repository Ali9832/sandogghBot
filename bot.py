import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از .env (در صورت وجود لوکال)
load_dotenv()

# خروجی استاندارد بدون بافر برای مشاهده بلادرنگ لاگ‌ها در رانفلر
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8080"))

# استخر رشته‌ها برای پردازش همزمان پیام‌ها
executor = ThreadPoolExecutor(max_workers=10)


# ─────────────────────────────────────────────
#  کیبوردها
# ─────────────────────────────────────────────

def main_menu_keyboard() -> dict:
    """کیبورد منوی اصلی – ۶ دکمه"""
    return {
        "keyboard": [
            [{"text": "👤 عضویت و حساب کاربری"}],
            [{"text": "💰 درخواست وام"}],
            [{"text": "💳 پرداختها و اقساط"}],
            [{"text": "🤲 خیریه و نذورات"}],
            [{"text": "⚔️ مشارکت جهادی"}],
            [{"text": "📊 گزارشها و پشتیبانی"}],
        ],
        "resize_keyboard": True,
    }


def reports_support_keyboard() -> dict:
    """کیبورد زیرمنوی گزارشها و پشتیبانی"""
    return {
        "keyboard": [
            [{"text": "📈 گزارش مالی"}],
            [{"text": "📋 گزارش فعالیتها"}],
            [{"text": "📢 اطلاعیهها"}],
            [{"text": "🛟 پشتیبانی"}],
            [{"text": "📜 قوانین صندوق"}],
            [{"text": "🔙 بازگشت به منوی اصلی"}],
        ],
        "resize_keyboard": True,
    }


# ─────────────────────────────────────────────
#  ارسال پیام
# ─────────────────────────────────────────────

def send_message(chat_id: int | str, text: str, reply_markup: dict | None = None) -> dict:
    """ارسال پیام به کاربر از طریق API رسمی بله"""
    if not BOT_TOKEN:
        logger.error("ارسال پیام ناموفق: BOT_TOKEN تنظیم نشده است.")
        return {}

    url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        if not data.get("ok"):
            logger.warning("ارسال ناموفق پیام به %s: %s", chat_id, data)
        return data
    except Exception as e:
        logger.error("خطا در ارسال پیام به %s: %s", chat_id, e)
        return {}


# ─────────────────────────────────────────────
#  پردازش پیام‌های دریافتی
# ─────────────────────────────────────────────

def handle_message(message: dict):
    """مدیریت رویداد دریافت پیام"""
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return

    text = message.get("text", "")

    # ── دستور شروع ──────────────────────────
    if text == "/start":
        send_message(
            chat_id,
            "سلام! به ربات صندوق خوش آمدید 🌟\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=main_menu_keyboard(),
        )

    # ── منوی اصلی ───────────────────────────
    elif text == "👤 عضویت و حساب کاربری":
        send_message(chat_id, "بخش عضویت و حساب کاربری در حال توسعه است... ⏳")

    elif text == "💰 درخواست وام":
        send_message(chat_id, "بخش درخواست وام در حال توسعه است... ⏳")

    elif text == "💳 پرداختها و اقساط":
        send_message(chat_id, "بخش پرداختها و اقساط در حال توسعه است... ⏳")

    elif text == "🤲 خیریه و نذورات":
        send_message(chat_id, "بخش خیریه و نذورات در حال توسعه است... ⏳")

    elif text == "⚔️ مشارکت جهادی":
        send_message(chat_id, "بخش مشارکت جهادی در حال توسعه است... ⏳")

    elif text == "📊 گزارشها و پشتیبانی":
        send_message(
            chat_id,
            "📊 بخش گزارشها و پشتیبانی\nیکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=reports_support_keyboard(),
        )

    # ── زیرمنوی گزارشها و پشتیبانی ─────────
    elif text == "📈 گزارش مالی":
        send_message(chat_id, "بخش گزارش مالی در حال توسعه است... ⏳")

    elif text == "📋 گزارش فعالیتها":
        send_message(chat_id, "بخش گزارش فعالیتها در حال توسعه است... ⏳")

    elif text == "📢 اطلاعیهها":
        send_message(chat_id, "بخش اطلاعیهها در حال توسعه است... ⏳")

    elif text == "🛟 پشتیبانی":
        send_message(chat_id, "بخش پشتیبانی در حال توسعه است... ⏳")

    elif text == "📜 قوانین صندوق":
        send_message(chat_id, "بخش قوانین صندوق در حال توسعه است... ⏳")

    elif text == "🔙 بازگشت به منوی اصلی":
        send_message(
            chat_id,
            "منوی اصلی:",
            reply_markup=main_menu_keyboard(),
        )


# ─────────────────────────────────────────────
#  سرور وب سبک برای Health Check و Webhook
# ─────────────────────────────────────────────

class BotWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """پاسخ به تست سلامت سرور رانفلر (Health Check)"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        response_data = {
            "status": "healthy",
            "bot": "sandoghtaavonibot",
            "message": "Service is running successfully",
        }
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def do_POST(self):
        """دریافت به‌روزرسانی‌های وب‌هوک از سرور بله"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            if "message" in data:
                executor.submit(handle_message, data["message"])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logger.error("خطا در پردازش درخواست وب‌هوک: %s", e)
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        # جلوگیری از شلوغ شدن لاگ‌ها توسط هلث‌چک‌های دوره‌ای
        pass


def run_http_server(port: int):
    """اجرای وب‌سرور برای پاس کردن تست سلامت رانفلر"""
    try:
        server = HTTPServer(("0.0.0.0", port), BotWebHandler)
        logger.info("✅ وب‌سرور سلامت سنجی روی پورت %s راه‌اندازی شد.", port)
        server.serve_forever()
    except Exception as e:
        logger.warning("نتوانست وب‌سرور پورت %s را باز کند: %s", port, e)


# ─────────────────────────────────────────────
#  حلقه Polling
# ─────────────────────────────────────────────

def start_polling():
    """حلقه مداوم دریافت پیام‌ها از بله"""
    offset = None
    logger.info("در حال شنود پیام‌ها از طریق Long-Polling...")

    while True:
        try:
            params = {"timeout": 20}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(
                f"https://tapi.bale.ai/bot{BOT_TOKEN}/getUpdates",
                params=params,
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        if "message" in update:
                            executor.submit(handle_message, update["message"])
                else:
                    logger.warning("خطا از سرور بله: %s", data)
                    time.sleep(2)
            else:
                logger.warning("کد وضعیت HTTP نامعتبر از سرور بله: %s", resp.status_code)
                time.sleep(3)

        except requests.exceptions.RequestException as e:
            logger.warning("خطای شبکه یا قطعی موقت بله: %s - تلاش مجدد در ۳ ثانیه...", e)
            time.sleep(3)
        except Exception as e:
            logger.error("خطای پیش‌بینی‌نشده در حلقه بات: %s", e, exc_info=True)
            time.sleep(3)


# ─────────────────────────────────────────────
#  اجرا (Main Entry)
# ─────────────────────────────────────────────

def run():
    global BOT_TOKEN, WEBHOOK_URL

    # ابتدا وب‌سرور هلث‌چک را در پس‌زمینه استارت می‌زنیم تا رانفلر کانتینر را نکشد
    threading.Thread(target=run_http_server, args=(PORT,), daemon=True).start()

    # بررسی تنظیم بودن BOT_TOKEN
    while not BOT_TOKEN:
        logger.critical(
            "❌ [خطای مهم] متغیر محیطی BOT_TOKEN در تنظیمات رانفلر یافت نشد!\n"
            "لطفاً وارد پنل Runflare شده، به بخش «متغیرها» (Variables) در سرویس خود بروید و متغیر BOT_TOKEN را اضافه کنید."
        )
        time.sleep(15)
        BOT_TOKEN = os.getenv("BOT_TOKEN")

    # بررسی اتصال به بات با متد getMe
    try:
        me_resp = requests.get(f"https://tapi.bale.ai/bot{BOT_TOKEN}/getMe", timeout=10)
        me_data = me_resp.json()
        if me_data.get("ok"):
            bot_info = me_data.get("result", {})
            logger.info(
                "ربات با موفقیت متصل شد: @%s (نام: %s)",
                bot_info.get("username"),
                bot_info.get("first_name"),
            )
        else:
            logger.warning("پاسخ getMe ناموفق بود: %s", me_data)
    except Exception as e:
        logger.error("خطا در برقراری ارتباط با سرور بله: %s", e)

    # اگر آدرس وبهوک ست شده باشد
    if WEBHOOK_URL:
        try:
            res = requests.post(
                f"https://tapi.bale.ai/bot{BOT_TOKEN}/setWebhook",
                json={"url": WEBHOOK_URL},
                timeout=10,
            )
            logger.info("✅ وبهوک خودکار ست شد: %s (پاسخ: %s)", WEBHOOK_URL, res.text)
        except Exception as e:
            logger.error("خطا در تنظیم وبهوک: %s", e)
        logger.info("حالت وبهوک فعال است. کانتینر برای دریافت پیام‌ها آماده است.")
        while True:
            time.sleep(3600)
    else:
        # حالت Long-Polling
        try:
            requests.post(f"https://tapi.bale.ai/bot{BOT_TOKEN}/deleteWebhook", timeout=10)
            logger.info("⚡ حالت long-polling فعال شد (وبهوک پاک شد)")
        except Exception as e:
            logger.warning("خطا در حذف وبهوک قبلی: %s", e)

        start_polling()


if __name__ == "__main__":
    run()
