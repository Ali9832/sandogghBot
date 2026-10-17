import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

API_BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

# استخر رشته‌ها برای پردازش همزمان پیام‌ها بدون بلاک شدن حلقه دریافت
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
    """ارسال پیام متنی به کاربر از طریق API رسمی بله"""
    url = f"{API_BASE_URL}/sendMessage"
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
#  اجرا (Run)
# ─────────────────────────────────────────────

def run():
    """شروع ربات و حلقه Long-Polling"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN در فایل .env یا متغیرهای محیطی تنظیم نشده است!")

    # بررسی هویت بات با متد getMe
    try:
        me_resp = requests.get(f"{API_BASE_URL}/getMe", timeout=10)
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

    # تنظیم یا حذف وبهوک
    if WEBHOOK_URL:
        try:
            res = requests.post(
                f"{API_BASE_URL}/setWebhook",
                json={"url": WEBHOOK_URL},
                timeout=10,
            )
            logger.info("✅ وبهوک خودکار ست شد: %s (پاسخ: %s)", WEBHOOK_URL, res.text)
        except Exception as e:
            logger.error("خطا در تنظیم وبهوک: %s", e)
        logger.info("حالت وبهوک فعال است.")
        return
    else:
        try:
            requests.post(f"{API_BASE_URL}/deleteWebhook", timeout=10)
            logger.info("⚡ حالت long-polling فعال شد (وبهوک حذف شد)")
        except Exception as e:
            logger.warning("خطا در حذف وبهوک قبلی: %s", e)

    offset = None
    logger.info("در حال شنود پیام‌ها...")

    while True:
        try:
            params = {"timeout": 20}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(
                f"{API_BASE_URL}/getUpdates",
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
                            # پردازش همزمان در ترد جداگانه
                            executor.submit(handle_message, update["message"])
                else:
                    logger.warning("خطا از سرور بله: %s", data)
                    time.sleep(2)
            else:
                logger.warning("کد وضعیت HTTP نامعتبر: %s", resp.status_code)
                time.sleep(3)

        except requests.exceptions.RequestException as e:
            logger.warning("خطای شبکه یا قطعی موقت: %s - تلاش مجدد در ۳ ثانیه...", e)
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("ربات متوقف شد.")
            break
        except Exception as e:
            logger.error("خطای پیش‌بینی‌نشده در حلقه بات: %s", e, exc_info=True)
            time.sleep(3)


if __name__ == "__main__":
    run()
