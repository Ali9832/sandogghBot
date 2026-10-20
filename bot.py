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
WEBSITE_URL = os.getenv(
    "WEBSITE_URL",
    "https://sandogh-hamyari.jauntyboar32.chatgpt.site",
)

# استخر رشته‌ها برای پردازش همزمان پیام‌ها
executor = ThreadPoolExecutor(max_workers=10)


# ─────────────────────────────────────────────
#  کیبوردها
# ─────────────────────────────────────────────

def build_keyboard(rows: list[list[str]]) -> dict:
    """ساخت کیبورد پاسخ از روی عنوان دکمه‌ها."""
    return {
        "keyboard": [[{"text": text} for text in row] for row in rows],
        "resize_keyboard": True,
    }


def main_menu_keyboard() -> dict:
    """کیبورد اصلی دو ستونه."""
    return build_keyboard(
        [
            ["👤 حساب و عضویت", "💰 وام و اقساط"],
            ["🤲 نذر و کمک", "🙋 داوطلبی و جهادی"],
            ["🧰 بانک خدمات", "📅 طرح‌ها و رویدادها"],
            ["📊 شفافیت و گزارش‌ها", "☎️ راهنما و پشتیبانی"],
        ]
    )


SUBMENU_KEYBOARDS = {
    "account": [
        ["📝 ثبت‌نام و تکمیل مشخصات", "🪪 وضعیت عضویت من"],
        ["💳 پرداخت حق عضویت", "🔄 مشارکت ثابت ماهانه"],
        ["📜 سوابق پرداخت‌های من", "✏️ ویرایش اطلاعات"],
        ["🎁 دعوت دوستان"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "loan": [
        ["📘 شرایط دریافت وام", "➕ درخواست وام جدید"],
        ["🔎 پیگیری درخواست", "📆 اقساط من"],
        ["💵 ثبت پرداخت قسط", "👥 ضمانت‌های من"],
        ["⏳ درخواست تعویق"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "donation": [
        ["❤️ کمک عمومی", "🎯 کمپین‌های فعال"],
        ["🍲 غذای گرم", "🛍 بسته معیشتی"],
        ["💍 کمک ازدواج", "📚 کمک آموزشی"],
        ["🧱 اردوی جهادی", "🎁 اهدای کالا یا خدمات"],
        ["🧾 سوابق و رسیدهای من"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "volunteer": [
        ["📝 ثبت‌نام داوطلب", "🛠 ثبت مهارت‌ها"],
        ["🕐 زمان‌های در دسترس", "📣 فراخوان‌های فعال"],
        ["✅ اعلام آمادگی", "📋 فعالیت‌های من"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "services": [
        ["🏪 فروشگاه‌ها و تأمین‌کنندگان", "⚖️ خدمات حقوقی"],
        ["🧠 مشاوره و روان‌شناسی", "🩺 درمان و دارو"],
        ["📚 آموزش و مهارت", "🔧 خدمات فنی"],
        ["➕ معرفی تأمین‌کننده"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "events": [
        ["🎯 پروژه‌های فعال", "🗓 تقویم رویدادها"],
        ["✅ ثبت‌نام در رویداد", "📢 اطلاعیه‌ها"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "reports": [
        ["💰 موجودی و گردش مالی", "📈 گزارش ماهانه"],
        ["🤝 وضعیت تجمیعی وام‌ها", "🎯 پیشرفت کمپین‌ها"],
        ["📷 گزارش تصویری پروژه‌ها", "📜 صورت‌جلسات"],
        ["⚖️ قوانین و اساسنامه"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
    "support": [
        ["❓ پرسش‌های متداول", "🎫 ثبت تیکت"],
        ["🌐 سایت صندوق", "📞 راه ارتباطی"],
        ["🔙 بازگشت به منوی اصلی"],
    ],
}


MAIN_MENU_SECTIONS = {
    "👤 حساب و عضویت": (
        "account",
        "👤 حساب و عضویت\nثبت‌نام، مشاهده وضعیت عضویت و مدیریت مشارکت‌های شما.",
    ),
    "💰 وام و اقساط": (
        "loan",
        "💰 وام و اقساط\nشرایط، درخواست جدید، پیگیری پرونده و برنامه بازپرداخت.",
    ),
    "🤲 نذر و کمک": (
        "donation",
        "🤲 نذر و کمک\nکمک عمومی، کمپین‌های مناسبتی و اهدای کالا یا خدمات.",
    ),
    "🙋 داوطلبی و جهادی": (
        "volunteer",
        "🙋 داوطلبی و جهادی\nمهارت و زمان آزاد خود را ثبت کنید یا فراخوان‌ها را ببینید.",
    ),
    "🧰 بانک خدمات": (
        "services",
        "🧰 بانک خدمات و امکانات\nتأمین‌کنندگان، متخصصان و خدمات همکار صندوق.",
    ),
    "📅 طرح‌ها و رویدادها": (
        "events",
        "📅 طرح‌ها و رویدادها\nپروژه‌های فعال، تقویم برنامه‌ها و ثبت‌نام رویدادها.",
    ),
    "📊 شفافیت و گزارش‌ها": (
        "reports",
        "📊 شفافیت و گزارش‌ها\nخروجی‌های مالی و اجرایی به‌صورت تجمیعی و بدون افشای اطلاعات خصوصی.",
    ),
    "☎️ راهنما و پشتیبانی": (
        "support",
        "☎️ راهنما و پشتیبانی\nپرسش‌های متداول، ارتباط با پشتیبانی و سایت صندوق.",
    ),
}


FEATURE_MESSAGES = {
    "📝 ثبت‌نام و تکمیل مشخصات": "فرم مرحله‌ای ثبت‌نام در فاز ۲ به پایگاه داده متصل می‌شود.",
    "🪪 وضعیت عضویت من": "پس از تکمیل ثبت‌نام، شماره و وضعیت عضویت شما اینجا نمایش داده می‌شود.",
    "💳 پرداخت حق عضویت": "پرداخت حق عضویت و صدور رسید دیجیتال در فاز ۳ فعال می‌شود.",
    "🔄 مشارکت ثابت ماهانه": "انتخاب مبلغ و دوره مشارکت ثابت در فاز ۳ فعال می‌شود.",
    "📜 سوابق پرداخت‌های من": "سوابق تأییدشده پرداخت‌ها پس از اتصال سامانه مالی نمایش داده می‌شود.",
    "✏️ ویرایش اطلاعات": "ویرایش کنترل‌شده اطلاعات عضو در فاز ۲ فعال می‌شود.",
    "🎁 دعوت دوستان": "لینک دعوت اختصاصی اعضا پس از راه‌اندازی حساب کاربری فعال می‌شود.",
    "📘 شرایط دریافت وام": "شرایط نهایی وام پس از تصویب اساسنامه و سیاست‌های صندوق منتشر می‌شود.",
    "➕ درخواست وام جدید": "گردش کامل درخواست وام، ضامن و مدارک در فاز ۴ فعال می‌شود.",
    "🔎 پیگیری درخواست": "پس از ثبت درخواست، با کد رهگیری می‌توانید وضعیت پرونده را ببینید.",
    "📆 اقساط من": "جدول اقساط و سررسیدها در فاز ۴ نمایش داده می‌شود.",
    "💵 ثبت پرداخت قسط": "ثبت و تطبیق پرداخت قسط در فاز ۴ فعال می‌شود.",
    "👥 ضمانت‌های من": "پرونده‌هایی که ضمانت کرده‌اید در فاز ۴ قابل مشاهده خواهند بود.",
    "⏳ درخواست تعویق": "درخواست بررسی تعویق یا تغییر سررسید در فاز ۴ فعال می‌شود.",
    "🎫 ثبت تیکت": "سامانه پیگیری پشتیبانی در فاز ۲ فعال می‌شود.",
    "🌐 سایت صندوق": f"مرکز معرفی و خروجی‌های صندوق:\n{WEBSITE_URL}",
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

    text = message.get("text", "").strip()

    # ── دستورهای اصلی ───────────────────────
    if text.startswith("/start") or text == "/menu":
        send_message(
            chat_id,
            "سلام! به صندوق همیاری دانشجویی خوش آمدید 🌱\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text in {"/help", "راهنما"}:
        send_message(
            chat_id,
            "راهنمای نسخه آزمایشی:\n"
            "• برای نمایش منوی اصلی /menu را بفرستید.\n"
            "• برای حرکت بین بخش‌ها از دکمه‌های پایین صفحه استفاده کنید.\n"
            "• امکانات عملیاتی به‌ترتیب فازهای توسعه فعال می‌شوند.\n\n"
            f"سایت پروژه: {WEBSITE_URL}",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text == "🔙 بازگشت به منوی اصلی":
        send_message(
            chat_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── منوهای سطح اول ──────────────────────
    section = MAIN_MENU_SECTIONS.get(text)
    if section:
        keyboard_name, description = section
        send_message(
            chat_id,
            f"{description}\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=build_keyboard(SUBMENU_KEYBOARDS[keyboard_name]),
        )
        return

    # ── گزینه‌های دارای پیام اختصاصی ────────
    feature_message = FEATURE_MESSAGES.get(text)
    if feature_message:
        send_message(chat_id, f"{feature_message}\n\n⏳ این قابلیت در نسخه عملیاتی فعال خواهد شد.")
        return

    # ── سایر گزینه‌های طراحی‌شده فاز یک ─────
    known_buttons = {
        button
        for rows in SUBMENU_KEYBOARDS.values()
        for row in rows
        for button in row
    }
    if text in known_buttons:
        send_message(
            chat_id,
            "این مسیر در فاز یک طراحی شده و پس از اتصال هسته داده، "
            "فرم و اطلاعات واقعی آن فعال می‌شود. ⏳",
        )
        return

    if text:
        send_message(
            chat_id,
            "پیام شما دریافت شد. برای ادامه از منوی زیر استفاده کنید یا /help را بفرستید.",
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
