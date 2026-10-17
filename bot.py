import asyncio
import logging
from os import getenv

import bale
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = getenv("BOT_TOKEN")
WEBHOOK_URL = getenv("WEBHOOK_URL")  # اگه ست باشه، ربات خودکار وبهوک رو ست می‌کنه


# ─────────────────────────────────────────────
#  کیبوردها
# ─────────────────────────────────────────────

def main_menu_keyboard() -> bale.MenuKeyboardMarkup:
    """کیبورد منوی اصلی – ۶ دکمه"""
    keyboard = bale.MenuKeyboardMarkup()
    keyboard.add(bale.MenuKeyboardButton("👤 عضویت و حساب کاربری"), row=1)
    keyboard.add(bale.MenuKeyboardButton("💰 درخواست وام"), row=2)
    keyboard.add(bale.MenuKeyboardButton("💳 پرداختها و اقساط"), row=3)
    keyboard.add(bale.MenuKeyboardButton("🤲 خیریه و نذورات"), row=4)
    keyboard.add(bale.MenuKeyboardButton("⚔️ مشارکت جهادی"), row=5)
    keyboard.add(bale.MenuKeyboardButton("📊 گزارشها و پشتیبانی"), row=6)
    return keyboard


def reports_support_keyboard() -> bale.MenuKeyboardMarkup:
    """کیبورد زیرمنوی گزارشها و پشتیبانی"""
    keyboard = bale.MenuKeyboardMarkup()
    keyboard.add(bale.MenuKeyboardButton("📈 گزارش مالی"), row=1)
    keyboard.add(bale.MenuKeyboardButton("📋 گزارش فعالیتها"), row=2)
    keyboard.add(bale.MenuKeyboardButton("📢 اطلاعیهها"), row=3)
    keyboard.add(bale.MenuKeyboardButton("🛟 پشتیبانی"), row=4)
    keyboard.add(bale.MenuKeyboardButton("📜 قوانین صندوق"), row=5)
    keyboard.add(bale.MenuKeyboardButton("🔙 بازگشت به منوی اصلی"), row=6)
    return keyboard


# ─────────────────────────────────────────────
#  ساخت ربات
# ─────────────────────────────────────────────

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN در فایل .env تنظیم نشده است!")

bot = bale.Bot(token=BOT_TOKEN)


# ─────────────────────────────────────────────
#  هندلرها
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info("ربات در حال اجرا: %s", bot.user.username)
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info("✅ وبهوک خودکار ست شد: %s", WEBHOOK_URL)
    else:
        await bot.delete_webhook()
        logger.info("⚡ حالت long-polling فعال شد (بدون وبهوک)")


@bot.event
async def on_message(message: bale.Message):
    text = message.text or ""

    # ── دستور شروع ──────────────────────────
    if text == "/start":
        await message.reply(
            "سلام! به ربات صندوق خوش آمدید 🌟\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            components=main_menu_keyboard(),
        )

    # ── منوی اصلی ───────────────────────────
    elif text == "👤 عضویت و حساب کاربری":
        await message.reply("بخش عضویت و حساب کاربری در حال توسعه است... ⏳")

    elif text == "💰 درخواست وام":
        await message.reply("بخش درخواست وام در حال توسعه است... ⏳")

    elif text == "💳 پرداختها و اقساط":
        await message.reply("بخش پرداختها و اقساط در حال توسعه است... ⏳")

    elif text == "🤲 خیریه و نذورات":
        await message.reply("بخش خیریه و نذورات در حال توسعه است... ⏳")

    elif text == "⚔️ مشارکت جهادی":
        await message.reply("بخش مشارکت جهادی در حال توسعه است... ⏳")

    elif text == "📊 گزارشها و پشتیبانی":
        await message.reply(
            "📊 بخش گزارشها و پشتیبانی\nیکی از گزینه‌های زیر را انتخاب کنید:",
            components=reports_support_keyboard(),
        )

    # ── زیرمنوی گزارشها و پشتیبانی ─────────
    elif text == "📈 گزارش مالی":
        await message.reply("بخش گزارش مالی در حال توسعه است... ⏳")

    elif text == "📋 گزارش فعالیتها":
        await message.reply("بخش گزارش فعالیتها در حال توسعه است... ⏳")

    elif text == "📢 اطلاعیهها":
        await message.reply("بخش اطلاعیهها در حال توسعه است... ⏳")

    elif text == "🛟 پشتیبانی":
        await message.reply("بخش پشتیبانی در حال توسعه است... ⏳")

    elif text == "📜 قوانین صندوق":
        await message.reply("بخش قوانین صندوق در حال توسعه است... ⏳")

    elif text == "🔙 بازگشت به منوی اصلی":
        await message.reply(
            "منوی اصلی:",
            components=main_menu_keyboard(),
        )


# ─────────────────────────────────────────────
#  اجرا
# ─────────────────────────────────────────────

def run():
    bot.run()

if __name__ == "__main__":
    run()
