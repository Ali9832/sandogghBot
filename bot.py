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

from database import Member, MemberRepository

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
BOT_USERNAME = os.getenv("BOT_USERNAME", "sandoghtaavonibot").lstrip("@")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/sandogh.db")

_member_repository: MemberRepository | None = None


def get_member_repository() -> MemberRepository:
    global _member_repository
    if _member_repository is None:
        _member_repository = MemberRepository(DATABASE_PATH)
    return _member_repository

# استخر رشته‌ها برای پردازش همزمان پیام‌ها
executor = ThreadPoolExecutor(max_workers=10)


# ─────────────────────────────────────────────
#  رابط تعاملی فاز یک
# ─────────────────────────────────────────────

Button = tuple[str, str]


def build_inline_keyboard(rows: list[list[Button]]) -> dict:
    """ساخت دکمه‌های شیشه‌ای؛ مقصدهای url: به‌صورت لینک باز می‌شوند."""
    keyboard = []
    for row in rows:
        keyboard_row = []
        for text, target in row:
            if target.startswith("url:"):
                keyboard_row.append({"text": text, "url": target.removeprefix("url:")})
            else:
                keyboard_row.append({"text": text, "callback_data": target})
        keyboard.append(keyboard_row)
    return {"inline_keyboard": keyboard}


MAIN_MENU_ROWS: list[list[Button]] = [
    [("👤 حساب و عضویت", "menu:account"), ("💰 وام و اقساط", "menu:loan")],
    [("🤲 نذر و کمک", "menu:donation"), ("🙋 داوطلبی و جهادی", "menu:volunteer")],
    [("🧰 بانک خدمات", "menu:services"), ("📅 طرح‌ها و رویدادها", "menu:events")],
    [("📊 شفافیت و گزارش‌ها", "menu:reports"), ("☎️ راهنما و پشتیبانی", "menu:support")],
    [("🌐 شبکه دانشگاهی", "menu:network"), ("🎓 آموزش و پادکست", "menu:learning")],
]


def main_menu_keyboard() -> dict:
    return build_inline_keyboard(MAIN_MENU_ROWS)


SECTION_DESCRIPTIONS = {
    "account": "👤 حساب و عضویت\nثبت‌نام، مشاهده وضعیت عضویت و مدیریت مشارکت‌های شما.",
    "loan": "💰 وام و اقساط\nشرایط، درخواست جدید، پیگیری پرونده و برنامه بازپرداخت.",
    "donation": "🤲 نذر و کمک\nکمک عمومی، کمپین‌های مناسبتی و معرفی نیازمند.",
    "volunteer": "🙋 داوطلبی و جهادی\nمهارت و زمان آزاد خود را ثبت کنید یا فراخوان‌ها را ببینید.",
    "services": "🧰 بانک خدمات و امکانات\nتأمین‌کنندگان، متخصصان و خدمات همکار صندوق.",
    "events": "📅 طرح‌ها و رویدادها\nپروژه‌های فعال، تقویم برنامه‌ها و ثبت‌نام رویدادها.",
    "reports": "📊 شفافیت و گزارش‌ها\nخروجی‌های تجمیعی بدون افشای اطلاعات خصوصی.",
    "support": "☎️ راهنما و پشتیبانی\nپرسش‌های متداول، ارتباط با پشتیبانی و سایت صندوق.",
    "network": "🌐 شبکه دانشگاهی\nتوسعه شعب محلی، همکاری بین صندوق‌ها و تقویت شبکه انسانی.",
    "learning": "🎓 آموزش و پادکست\nکارگاه‌های پیشنهادی، محتوای آموزشی و موضوعات پادکست صندوق.",
}


SUBMENU_ROWS: dict[str, list[list[Button]]] = {
    "account": [
        [("📝 ثبت‌نام عضو", "member:start"), ("🪪 وضعیت عضویت من", "member:status")],
        [("💳 حق عضویت", "action:membership_fee"), ("🔄 مشارکت ثابت آزمایشی", "form:start:contribution")],
        [("📜 سوابق پرداخت", "action:payment_history"), ("✏️ ویرایش اطلاعات", "member:edit")],
        [("🎁 دعوت دوستان", "member:referral")],
    ],
    "loan": [
        [("📘 شرایط دریافت وام", "action:loan_terms"), ("➕ درخواست آزمایشی وام", "form:start:loan")],
        [("🔎 پیگیری درخواست", "action:loan_track"), ("📆 اقساط من", "action:installments")],
        [("💵 ثبت پرداخت قسط", "action:installment_pay"), ("👥 ضمانت‌های من", "action:guarantees")],
        [("⏳ درخواست تعویق", "action:deferment")],
    ],
    "donation": [
        [("❤️ ثبت کمک آزمایشی", "form:start:donation"), ("🎯 کمپین‌های فعال", "action:campaigns")],
        [("🍲 غذای گرم", "action:hot_food"), ("🛍 بسته معیشتی", "action:livelihood")],
        [("💍 کمک ازدواج", "action:marriage_help"), ("📚 کمک آموزشی", "action:education_help")],
        [("🧱 اردوی جهادی", "action:jihad_camp"), ("🎁 اهدای کالا یا خدمات", "action:goods_donation")],
        [("🫶 معرفی آزمایشی نیازمند", "form:start:beneficiary"), ("🧾 سوابق و رسیدها", "action:donation_history")],
    ],
    "volunteer": [
        [("📝 ثبت‌نام آزمایشی داوطلب", "form:start:volunteer"), ("🛠 ثبت مهارت‌ها", "action:skills")],
        [("🕐 زمان‌های در دسترس", "action:availability"), ("📣 فراخوان‌های فعال", "action:calls")],
        [("✅ اعلام آمادگی", "form:start:volunteer"), ("📋 فعالیت‌های من", "action:activities")],
    ],
    "services": [
        [("🏪 فروشگاه‌ها و تأمین‌کنندگان", "action:suppliers"), ("⚖️ خدمات حقوقی", "action:legal")],
        [("🧠 مشاوره و روان‌شناسی", "action:counseling"), ("🩺 درمان و دارو", "action:health")],
        [("📚 آموزش و مهارت", "action:training"), ("🔧 خدمات فنی", "action:technical")],
        [("➕ معرفی آزمایشی تأمین‌کننده", "form:start:supplier")],
    ],
    "events": [
        [("🎯 پروژه‌های فعال", "action:projects"), ("🗓 تقویم رویدادها", "action:calendar")],
        [("✅ ثبت‌نام آزمایشی رویداد", "form:start:event"), ("📢 اطلاعیه‌ها", "action:notices")],
    ],
    "network": [
        [("🌱 پایداری و توسعه ملی", "action:phase4_roadmap"), ("💡 ایده کسب‌وکار اجتماعی", "form:start:enterprise")],
        [("📋 ایده‌های ثبت‌شدهٔ من", "phase4:my_enterprises")],
        [("📍 شعب دانشگاهی", "action:branches"), ("🤝 همکاری بین صندوق‌ها", "action:partner_funds")],
        [("🧭 کمیته‌های محلی", "action:local_committees"), ("➕ اعلام آمادگی برای شعبه", "form:start:branch")],
        [("📋 علاقه‌مندی شعبهٔ من", "phase3:my_branches")],
    ],
    "learning": [
        [("🧑‍🏫 علاقه‌مندی به کارگاه", "form:start:workshop"), ("🎙 موضوعات پادکست", "action:podcast")],
        [("📹 محتوای آموزشی کوتاه", "action:learning_content"), ("📚 راهنما و پایگاه دانش", "action:knowledge_base")],
        [("📋 علاقه‌مندی‌های کارگاهی من", "phase3:my_workshops")],
    ],
    "reports": [
        [("💰 موجودی و گردش مالی", "action:balance"), ("📈 گزارش ماهانه", "action:monthly_report")],
        [("🤝 وضعیت تجمیعی وام‌ها", "action:loan_report"), ("🎯 پیشرفت کمپین‌ها", "action:campaign_report")],
        [("📷 گزارش تصویری پروژه‌ها", "action:photo_report"), ("📜 صورت‌جلسات", "action:minutes")],
        [("⚖️ قوانین و اساسنامه", "action:rules")],
    ],
    "support": [
        [("❓ پرسش‌های متداول", "action:faq"), ("🎫 تیکت آزمایشی", "form:start:support")],
        [("🌐 سایت صندوق", f"url:{WEBSITE_URL}"), ("📞 راه ارتباطی", "action:contact")],
    ],
}


def submenu_keyboard(section: str) -> dict:
    rows = list(SUBMENU_ROWS[section])
    rows.append([("🏠 منوی اصلی", "menu:main")])
    return build_inline_keyboard(rows)


ACTION_MESSAGES = {
    "membership_fee": "در فاز ۱ هیچ پرداختی دریافت نمی‌شود؛ این بخش فقط پیش‌نمایش است.",
    "payment_history": "پس از اتصال سامانه مالی، سوابق تأییدشده اینجا نمایش داده می‌شود.",
    "loan_terms": "نمونه شرایط: سابقه عضویت، معرفی ضامن و بررسی کمیته؛ ارقام نهایی پس از تصویب اساسنامه اعلام می‌شوند.",
    "loan_track": "پیگیری واقعی پس از اتصال پرونده‌های وام و کد رهگیری فعال می‌شود.",
    "installments": "جدول اقساط و سررسیدها در فاز عملیاتی وام نمایش داده می‌شود.",
    "installment_pay": "در این نسخه هیچ پرداخت یا رسید بانکی دریافت نمی‌شود.",
    "guarantees": "فهرست ضمانت‌ها پس از احراز هویت و راه‌اندازی پرونده‌ها فعال می‌شود.",
    "deferment": "گردش بررسی تعویق در فاز عملیاتی وام فعال می‌شود.",
    "campaigns": "کمپین‌های نمونه: غذای گرم، بسته معیشتی، کمک آموزشی و اردوی جهادی.",
    "hot_food": "پیش‌نمایش طرح غذای گرم؛ پرداخت و ثبت کمک واقعی غیرفعال است.",
    "livelihood": "پیش‌نمایش طرح بسته معیشتی؛ اطلاعات نیازمندان نمایش داده نمی‌شود.",
    "marriage_help": "پیش‌نمایش حمایت ازدواج و تأمین اقلام ضروری.",
    "education_help": "پیش‌نمایش حمایت آموزشی و تهیه اقلام تحصیلی.",
    "jihad_camp": "پیش‌نمایش اردوهای جهادی و گزارش اجرای طرح‌ها.",
    "goods_donation": "ثبت واقعی کالا و خدمات پس از فعال‌شدن واحد هماهنگی انجام می‌شود.",
    "donation_history": "سوابق کمک پس از اتصال پرداخت و صدور رسید قابل مشاهده خواهد بود.",
    "skills": "مهارت‌ها در فرم آزمایشی داوطلبی انتخاب می‌شوند.",
    "availability": "زمان آزاد در فرم آزمایشی داوطلبی انتخاب می‌شود.",
    "calls": "در حال حاضر فراخوان عملیاتی فعالی ثبت نشده است.",
    "activities": "سوابق فعالیت پس از ایجاد حساب داوطلب نمایش داده می‌شود.",
    "suppliers": "بانک خدمات شامل فروشگاه‌ها، متخصصان و تأمین‌کنندگان همکار خواهد بود.",
    "legal": "پیش‌نمایش خدمات حقوقی و وکالتی همکاران صندوق.",
    "counseling": "پیش‌نمایش خدمات مشاوره خانواده، تحصیل و روان‌شناسی.",
    "health": "پیش‌نمایش درمانگاه‌ها و داروخانه‌های همکار.",
    "training": "پیش‌نمایش کارگاه‌های آموزشی و مهارتی.",
    "technical": "پیش‌نمایش خدمات فنی و رایانه‌ای همکاران.",
    "projects": "پروژه‌های نمونه: بسته معیشتی، غذای گرم و اردوی جهادی.",
    "calendar": "تقویم واقعی پس از تصویب برنامه اجرایی منتشر می‌شود.",
    "notices": "اطلاعیه‌های رسمی صندوق در این بخش نمایش داده خواهند شد.",
    "balance": "در فاز ۱ عدد مالی واقعی نمایش داده نمی‌شود.",
    "monthly_report": "قالب گزارش ماهانه شامل مجموع ورودی، خروجی و عملکرد طرح‌ها خواهد بود.",
    "loan_report": "فقط آمار تجمیعی وام‌ها و بدون نام افراد منتشر خواهد شد.",
    "campaign_report": "میزان پیشرفت کمپین‌ها پس از اتصال داده‌های مالی نمایش داده می‌شود.",
    "photo_report": "گزارش تصویری با حفظ حریم خصوصی ذی‌نفعان منتشر خواهد شد.",
    "minutes": "صورت‌جلسات عمومی پس از تصویب هیئت‌مدیره منتشر می‌شوند.",
    "rules": "نسخه نهایی قوانین و اساسنامه پس از تصویب در دسترس قرار می‌گیرد.",
    "faq": "پرسش‌های پرتکرار: نحوه عضویت، شرایط وام، مشارکت، داوطلبی و گزارش‌دهی.",
    "contact": "راه ارتباطی رسمی پس از تعیین مسئول پشتیبانی اعلام می‌شود.",
    "branches": "در حال حاضر شعبهٔ دانشگاهی تأییدشده‌ای در سامانه ثبت نشده است. اگر عضو صندوق هستید، از گزینهٔ «اعلام آمادگی برای شعبه» استفاده کنید.",
    "partner_funds": "طرح فاز ۳ بر تبادل تجربه و اجرای پروژه‌های مشترک با صندوق‌های دانشگاهی دیگر تأکید دارد؛ همکاری رسمی پس از تأیید مسئولان ثبت می‌شود.",
    "local_committees": "برای هر دانشگاه، تشکیل کمیتهٔ محلی با نظارت متولی اصلی پیش‌بینی شده است. علاقه‌مندی خود را از مسیر «اعلام آمادگی برای شعبه» ثبت کنید.",
    "podcast": "🎙 موضوعات پیشنهادی پادکست صندوق:\n• داستان شکل‌گیری صندوق و همیاری دانشجویی\n• سواد و مدیریت مالی دانشجویی\n• تجربهٔ اردوهای جهادی و کار فرهنگی\n• گفت‌وگو با خیرین و فعالان\n\nاین‌ها موضوعات پیشنهادی‌اند؛ هنوز فایل یا قسمت منتشرشده‌ای ثبت نشده است.",
    "learning_content": "موضوعات پیشنهادی محتوای کوتاه: صرفه‌جویی دانشجویی، راهنمای عضویت، سواد مالی، کارگاه‌های مهارتی و راهنمای مشارکت در اردوها. محتوای منتشرشده پس از تأیید و افزودن پیوند رسمی نمایش داده می‌شود.",
    "knowledge_base": "راهنماهای مرحله‌ای در حال آماده‌سازی‌اند: عضویت، اعلام علاقه‌مندی به کارگاه، معرفی دانشگاه برای توسعهٔ شعبه و مشارکت داوطلبانه.",
}

PHASE3_ACTIONS = {
    "branches", "partner_funds", "local_committees", "podcast",
    "learning_content", "knowledge_base",
}
ACTION_MESSAGES["phase4_roadmap"] = (
    "نقشهٔ راه فاز ۴: نهادینه‌سازی عملیات، توسعهٔ شبکهٔ دانشگاهی و بررسی ایده‌های کسب‌وکار اجتماعی. "
    "در این نسخه هیچ تأیید حقوقی، ثبت شرکت یا فعالیت مالی انجام نمی‌شود."
)
PHASE4_ACTIONS = {"phase4_roadmap"}
ENTERPRISE_IDEA_LABELS = {
    "student_market": "بازارچهٔ دانشجویی",
    "education_services": "خدمات آموزشی و مهارتی",
    "digital_services": "خدمات فنی و دیجیتال",
    "local_supply": "تأمین محلی و زنجیرهٔ خیر",
}
ENTERPRISE_CONTRIBUTION_LABELS = {
    "ideation": "ایده‌پردازی و بررسی",
    "operations": "همکاری اجرایی",
    "networking": "معرفی همکار یا متخصص",
}


FORM_SPECS = {
    "contribution": {
        "title": "🔄 فرم آزمایشی مشارکت ثابت",
        "section": "account",
        "steps": [
            ("level", "سطح مشارکت نمونه را انتخاب کنید.", [("همراه", "companion"), ("همیار", "helper"), ("پشتیبان", "backer")]),
            ("period", "دورهٔ نمونه؟", [("۶ ماهه", "6m"), ("۱۲ ماهه", "12m"), ("قابل تغییر", "flexible")]),
        ],
    },
    "loan": {
        "title": "➕ فرم آزمایشی درخواست وام",
        "section": "loan",
        "steps": [
            ("type", "نوع وام نمونه را انتخاب کنید.", [("ضروری", "urgent"), ("ازدواج", "marriage"), ("کارآفرینی", "business")]),
            ("amount", "بازه مبلغ نمونه؟", [("تا ۵ میلیون", "5m"), ("۵ تا ۲۰ میلیون", "20m"), ("بیشتر از ۲۰ میلیون", "20m_plus")]),
            ("repayment", "دوره بازپرداخت نمونه؟", [("۶ ماه", "6m"), ("۱۲ ماه", "12m"), ("۱۸ ماه", "18m")]),
        ],
    },
    "donation": {
        "title": "❤️ فرم آزمایشی نذر و کمک",
        "section": "donation",
        "steps": [
            ("purpose", "کمک برای کدام حوزه باشد؟", [("عمومی", "general"), ("غذای گرم", "food"), ("بسته معیشتی", "livelihood"), ("آموزشی", "education")]),
            ("amount", "بازه کمک نمونه را انتخاب کنید.", [("کمتر از ۱۰۰ هزار", "under100"), ("۱۰۰ تا ۵۰۰ هزار", "500"), ("بیشتر از ۵۰۰ هزار", "over500")]),
            ("display", "نحوه نمایش در گزارش؟", [("بی‌نام", "anonymous"), ("فقط با رضایت", "consent")]),
        ],
    },
    "beneficiary": {
        "title": "🫶 فرم آزمایشی معرفی نیازمند",
        "section": "donation",
        "steps": [
            ("need", "حوزه نیاز چیست؟", [("معیشتی", "livelihood"), ("درمانی", "medical"), ("آموزشی", "education")]),
            ("relation", "نحوه آشنایی شما؟", [("معرف شخصی", "personal"), ("نهاد معتبر", "organization"), ("داوطلب محلی", "local")]),
            ("urgency", "میزان فوریت؟", [("عادی", "normal"), ("فوری", "urgent")]),
        ],
    },
    "volunteer": {
        "title": "🙋 فرم آزمایشی داوطلبی",
        "section": "volunteer",
        "steps": [
            ("skill", "حوزه مهارت؟", [("آموزشی", "education"), ("فنی", "technical"), ("فرهنگی", "cultural"), ("پشتیبانی", "support")]),
            ("availability", "زمان همکاری؟", [("هفتگی", "weekly"), ("ماهانه", "monthly"), ("موردی", "occasional")]),
            ("mode", "شیوه همکاری؟", [("حضوری", "in_person"), ("آنلاین", "online"), ("هردو", "both")]),
        ],
    },
    "supplier": {
        "title": "🏪 فرم آزمایشی معرفی تأمین‌کننده",
        "section": "services",
        "steps": [
            ("category", "دسته خدمت؟", [("فروشگاهی", "store"), ("درمانی", "health"), ("حقوقی", "legal"), ("فنی", "technical")]),
            ("cooperation", "نوع همکاری پیشنهادی؟", [("تخفیف", "discount"), ("اهدای خدمت", "donation"), ("خرید اعتباری", "credit")]),
        ],
    },
    "event": {
        "title": "📅 فرم آزمایشی رویداد",
        "section": "events",
        "steps": [
            ("event", "نوع رویداد؟", [("اردوی جهادی", "camp"), ("کارگاه", "workshop"), ("توزیع بسته", "distribution")]),
            ("role", "نقش شما؟", [("شرکت‌کننده", "participant"), ("داوطلب", "volunteer"), ("حامی", "sponsor")]),
        ],
    },
    "support": {
        "title": "🎫 فرم آزمایشی پشتیبانی",
        "section": "support",
        "steps": [
            ("topic", "موضوع درخواست؟", [("عضویت", "membership"), ("وام", "loan"), ("کمک", "donation"), ("پیشنهاد", "suggestion")]),
            ("priority", "اولویت؟", [("عادی", "normal"), ("مهم", "important")]),
        ],
    },
    "workshop": {
        "title": "🧑‍🏫 اعلام علاقه‌مندی کارگاه",
        "section": "learning",
        "persist": "workshop_interest",
        "steps": [
            ("topic", "به کدام حوزه علاقه‌مندید؟", [
                ("برنامه‌نویسی", "programming"),
                ("گرافیک و ویدئو", "design_video"),
                ("بازاریابی دیجیتال", "digital_marketing"),
                ("سواد مالی", "financial_literacy"),
                ("مهارت‌های نرم", "soft_skills"),
                ("مهارت‌های زندگی", "life_skills"),
            ]),
            ("attendance", "شیوهٔ برگزاری مناسب شما؟", [
                ("آنلاین", "online"), ("حضوری", "in_person"), ("فرقی ندارد", "either"),
            ]),
        ],
    },
    "enterprise": {
        "title": "🌱 اعلام علاقه‌مندی به ایدهٔ کسب‌وکار اجتماعی",
        "section": "network",
        "persist": "enterprise_interest",
        "steps": [
            ("idea_type", "به کدام حوزه علاقه دارید؟", [
                ("محصولات و بازارچهٔ دانشجویی", "student_market"),
                ("خدمات آموزشی و مهارتی", "education_services"),
                ("خدمات فنی و دیجیتال", "digital_services"),
                ("تأمین محلی و زنجیرهٔ خیر", "local_supply"),
            ]),
            ("contribution", "نقش پیشنهادی شما چیست؟", [
                ("ایده‌پردازی و بررسی", "ideation"),
                ("همکاری اجرایی", "operations"),
                ("معرفی همکار یا متخصص", "networking"),
            ]),
        ],
    },
    "branch": {
        "title": "🌐 اعلام آمادگی برای شعبهٔ دانشگاهی",
        "section": "network",
        "persist": "branch_interest",
        "requires_member": True,
        "steps": [
            ("team_role", "در چه بخشی می‌توانید همکاری کنید؟", [
                ("هماهنگی محلی", "local_coordination"),
                ("برگزاری کارگاه", "workshops"),
                ("فعالیت جهادی و فرهنگی", "community_projects"),
            ]),
            ("availability", "میزان دسترسی شما؟", [
                ("ماهانه", "monthly"), ("موردی", "occasional"), ("آنلاین", "online"),
            ]),
        ],
    },
}

FORM_SESSIONS: dict[tuple[str, str], dict] = {}
FORM_LOCK = threading.Lock()
MEMBER_SESSIONS: dict[tuple[str, str], dict] = {}
PENDING_REFERRALS: dict[tuple[str, str], str] = {}
MEMBER_LOCK = threading.Lock()

WORKSHOP_TOPIC_LABELS = {
    "programming": "برنامه‌نویسی",
    "design_video": "گرافیک و ویدئو",
    "digital_marketing": "بازاریابی دیجیتال",
    "financial_literacy": "سواد مالی",
    "soft_skills": "مهارت‌های نرم",
    "life_skills": "مهارت‌های زندگی",
}
ATTENDANCE_LABELS = {"online": "آنلاین", "in_person": "حضوری", "either": "فرقی ندارد"}
BRANCH_ROLE_LABELS = {
    "local_coordination": "هماهنگی محلی",
    "workshops": "برگزاری کارگاه",
    "community_projects": "فعالیت جهادی و فرهنگی",
}
AVAILABILITY_LABELS = {"monthly": "ماهانه", "occasional": "موردی", "online": "آنلاین"}

MEMBER_CHOICES = {
    "role": [("دانشجو", "student"), ("دانش‌آموخته", "graduate"), ("حامی", "supporter")],
    "participation": [("عضو", "member"), ("داوطلب", "volunteer"), ("حامی مالی", "donor")],
    "notification": [("همه پیام‌ها", "all"), ("فقط مهم", "important")],
}
MEMBER_FIELD_LABELS = {
    "display_name": "نام نمایشی",
    "university": "دانشگاه/مرکز آموزشی",
    "role": "نقش",
    "participation": "نوع مشارکت",
    "notification": "اعلان‌ها",
}
MEMBER_STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "active": "فعال",
    "suspended": "تعلیق‌شده",
}


def form_session_key(chat_id: int | str, user_id: int | str | None) -> tuple[str, str]:
    return str(chat_id), str(user_id or chat_id)


def choice_label(field: str, value: str) -> str:
    return dict(MEMBER_CHOICES.get(field, [])).get(value, value)


def member_profile_text(member: Member) -> str:
    return (
        "🪪 وضعیت عضویت شما\n\n"
        f"شماره عضویت: {member.membership_number}\n"
        f"نام نمایشی: {member.display_name}\n"
        f"دانشگاه/مرکز: {member.university}\n"
        f"نقش: {choice_label('role', member.role)}\n"
        f"نوع مشارکت: {choice_label('participation', member.participation)}\n"
        f"اعلان‌ها: {choice_label('notification', member.notification)}\n"
        f"وضعیت: {MEMBER_STATUS_LABELS.get(member.status, member.status)}\n\n"
        "برای حفظ حریم خصوصی، کد ملی، شماره کارت و مدرک هویتی دریافت نشده است."
    )


def member_summary_text(state: dict) -> str:
    answers = state["answers"]
    return (
        "📝 پیش‌نمایش ثبت‌نام\n\n"
        f"نام نمایشی: {answers['display_name']}\n"
        f"دانشگاه/مرکز: {answers['university']}\n"
        f"نقش: {choice_label('role', answers['role'])}\n"
        f"نوع مشارکت: {choice_label('participation', answers['participation'])}\n"
        f"اعلان‌ها: {choice_label('notification', answers['notification'])}\n\n"
        "با تأیید، این اطلاعات حداقلی در پایگاه داده صندوق ذخیره می‌شود."
    )


def member_choice_keyboard(
    field: str,
    prefix: str = "member:pick",
    back_callback: str | None = "member:back",
) -> dict:
    rows = []
    choices = MEMBER_CHOICES[field]
    for index in range(0, len(choices), 2):
        rows.append([
            (label, f"{prefix}:{field}:{value}")
            for label, value in choices[index:index + 2]
        ])
    navigation = []
    if back_callback:
        navigation.append(("⬅️ مرحله قبل", back_callback))
    navigation.append(("❌ لغو", "member:cancel"))
    rows.append(navigation)
    return build_inline_keyboard(rows)


def form_screen(state: dict) -> tuple[str, dict]:
    spec = FORM_SPECS[state["flow"]]
    step_index = state["step"]
    if step_index < len(spec["steps"]):
        key, prompt, options = spec["steps"][step_index]
        rows = []
        for index in range(0, len(options), 2):
            row = [
                (label, f"form:pick:{state['flow']}:{key}:{value}")
                for label, value in options[index:index + 2]
            ]
            rows.append(row)
        nav = []
        if step_index:
            nav.append(("⬅️ مرحله قبل", "form:back"))
        nav.append(("❌ لغو", "form:cancel"))
        rows.append(nav)
        text = (
            f"{spec['title']}\n"
            f"مرحله {step_index + 1} از {len(spec['steps'])}\n\n{prompt}\n\n"
            + (
                "🔒 با تأیید نهایی، فقط علاقه‌مندی انتخاب‌شده و شناسهٔ بله برای پیگیری ذخیره می‌شود؛ "
                "پرداخت یا اطلاعات هویتی دریافت نمی‌شود."
                if spec.get("persist")
                else "🔒 این فرم نمایشی است؛ هیچ اطلاعات شخصی یا مالی ذخیره نمی‌شود."
            )
        )
        return text, build_inline_keyboard(rows)

    summary = []
    for key, prompt, options in spec["steps"]:
        labels = {value: label for label, value in options}
        summary.append(f"• {prompt} {labels.get(state['answers'].get(key), '—')}")
    text = (
        f"{spec['title']}\nپیش‌نمایش نهایی:\n\n" + "\n".join(summary) +
        (
            "\n\nبا انتخاب «ثبت علاقه‌مندی»، شناسهٔ بله و همین انتخاب‌ها ذخیره می‌شوند. "
            "این ثبت، پذیرش نهایی در کارگاه/شعبه یا دریافت وجه نیست."
            if spec.get("persist")
            else "\n\nبا تأیید، فقط نتیجه نمایشی نشان داده می‌شود و چیزی ذخیره نخواهد شد."
        )
    )
    confirm_label = "✅ ثبت علاقه‌مندی" if spec.get("persist") else "✅ تأیید نمایشی"
    return text, build_inline_keyboard([
        [(confirm_label, "form:confirm")],
        [("⬅️ مرحله قبل", "form:back"), ("❌ لغو", "form:cancel")],
    ])


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


def edit_message(
    chat_id: int | str,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> dict:
    """ویرایش همان پیام برای جلوگیری از شلوغ‌شدن گفتگو."""
    if not BOT_TOKEN:
        return {}
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(
            f"https://tapi.bale.ai/bot{BOT_TOKEN}/editMessageText",
            json=payload,
            timeout=15,
        )
        data = response.json()
        if not data.get("ok"):
            logger.warning("ویرایش پیام ناموفق بود: %s", data)
        return data
    except Exception as e:
        logger.error("خطا در ویرایش پیام: %s", e)
        return {}


def answer_callback_query(callback_query_id: str, text: str | None = None) -> dict:
    """پایان‌دادن به حالت انتظار دکمه شیشه‌ای."""
    if not BOT_TOKEN or not callback_query_id:
        return {}
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        response = requests.post(
            f"https://tapi.bale.ai/bot{BOT_TOKEN}/answerCallbackQuery",
            json=payload,
            timeout=10,
        )
        return response.json()
    except Exception as e:
        logger.error("خطا در پاسخ به callback query: %s", e)
        return {}


def show_screen(
    chat_id: int | str,
    message_id: int | None,
    text: str,
    reply_markup: dict,
) -> None:
    """صفحه فعلی را ویرایش می‌کند و در صورت شکست، پیام تازه می‌فرستد."""
    if message_id:
        result = edit_message(chat_id, message_id, text, reply_markup)
        if result.get("ok"):
            return
    send_message(chat_id, text, reply_markup)


def normalize_profile_text(value: str, maximum: int) -> str | None:
    normalized = " ".join(value.split())
    if len(normalized) < 2 or len(normalized) > maximum:
        return None
    if any(ord(character) < 32 for character in normalized):
        return None
    return normalized


def process_member_text(message: dict) -> bool:
    """ورودی متنی محدود ثبت‌نام/ویرایش را پردازش می‌کند."""
    chat_id = (message.get("chat") or {}).get("id")
    user_id = (message.get("from") or {}).get("id") or chat_id
    text = str(message.get("text") or "").strip()
    if not chat_id or not text:
        return False
    session_key = form_session_key(chat_id, user_id)
    with MEMBER_LOCK:
        state = MEMBER_SESSIONS.get(session_key)
        if not state:
            return False
        step = state["step"]

    field = step.removeprefix("edit_")
    if field not in {"display_name", "university"}:
        return False
    maximum = 50 if field == "display_name" else 80
    normalized = normalize_profile_text(text, maximum)
    if normalized is None:
        send_message(
            chat_id,
            f"مقدار نامعتبر است. {MEMBER_FIELD_LABELS[field]} باید بین ۲ تا {maximum} نویسه باشد.\n"
            "برای خروج /cancel را بفرستید.",
        )
        return True

    if state["mode"] == "edit":
        member = get_member_repository().update_member(user_id, field, normalized)
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        if member:
            send_message(
                chat_id,
                f"✅ {MEMBER_FIELD_LABELS[field]} به‌روزرسانی شد.\n\n{member_profile_text(member)}",
                build_inline_keyboard([[("⬅️ حساب و عضویت", "menu:account")]]),
            )
        else:
            send_message(chat_id, "عضویت پیدا نشد.", submenu_keyboard("account"))
        return True

    with MEMBER_LOCK:
        state = MEMBER_SESSIONS.get(session_key)
        if not state:
            return True
        state["answers"][field] = normalized
        if field == "display_name":
            state["step"] = "university"
        else:
            state["step"] = "role"

    if field == "display_name":
        send_message(
            chat_id,
            "نام دانشگاه یا مرکز آموزشی را وارد کنید.\n"
            "اطلاعات هویتی، شماره دانشجویی یا کد ملی نفرستید.",
            build_inline_keyboard([[("⬅️ مرحله قبل", "member:back"), ("❌ لغو", "member:cancel")]]),
        )
    else:
        send_message(chat_id, "نقش خود را انتخاب کنید:", member_choice_keyboard("role"))
    return True


# ─────────────────────────────────────────────
#  پردازش پیام‌های دریافتی
# ─────────────────────────────────────────────

def handle_message(message: dict):
    """مدیریت پیام‌های متنی و فرمان‌های جایگزین."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return

    text = message.get("text", "").strip()
    user_id = (message.get("from") or {}).get("id") or chat_id
    session_key = form_session_key(chat_id, user_id)

    if text in {"/cancel", "لغو"}:
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        with FORM_LOCK:
            FORM_SESSIONS.pop(session_key, None)
        send_message(chat_id, "عملیات جاری لغو شد.", main_menu_keyboard())
        return

    # ── دستورهای اصلی ───────────────────────
    if text.startswith("/start"):
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        parts = text.split(maxsplit=1)
        referral_message = ""
        if len(parts) == 2 and parts[1].startswith("ref_"):
            referral_code = parts[1].removeprefix("ref_")
            if get_member_repository().get_by_referral_code(referral_code):
                with MEMBER_LOCK:
                    PENDING_REFERRALS[session_key] = referral_code
                referral_message = "\n🎁 دعوت‌نامه معتبر شناسایی شد؛ پس از ثبت‌نام برای معرف ثبت می‌شود."
            else:
                referral_message = "\n⚠️ کد دعوت معتبر نیست؛ می‌توانید بدون معرف ادامه دهید."
        send_message(
            chat_id,
            "سلام! به صندوق همیاری دانشجویی خوش آمدید 🌱\n"
            "نسخه تعاملی فاز ۲ فعال است. یکی از گزینه‌ها را انتخاب کنید:\n\n"
            "🔒 کد ملی، اطلاعات بانکی یا مدرک هویتی دریافت نمی‌شود."
            f"{referral_message}",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text == "/menu":
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        send_message(chat_id, "🏠 منوی اصلی", reply_markup=main_menu_keyboard())
        return

    if process_member_text(message):
        return

    if text in {"/help", "راهنما"}:
        send_message(
            chat_id,
            "راهنمای نسخه فاز ۲:\n"
            "• برای نمایش منوی اصلی /menu را بفرستید.\n"
            "• منوها و فرم‌های نمایشی با دکمه‌های شیشه‌ای کار می‌کنند.\n"
            "• با «مرحله قبل» و «لغو» می‌توانید در فرم حرکت کنید.\n"
            "• پاسخ فرم‌های نمایشی و هیچ اطلاعات پرداختی ذخیره نمی‌شود.\n"
            "• اطلاعات حداقلی عضویت فقط پس از رضایت شما ذخیره می‌شود.\n\n"
            f"سایت پروژه: {WEBSITE_URL}",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text in {"🔙 بازگشت به منوی اصلی", "🏠 منوی اصلی"}:
        send_message(
            chat_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu_keyboard(),
        )
        return

    # سازگاری با عنوان‌های منوی نسخه قبلی
    for section in SUBMENU_ROWS:
        menu_title = next(
            (label for row in MAIN_MENU_ROWS for label, target in row if target == f"menu:{section}"),
            None,
        )
        if text == menu_title:
            send_message(
                chat_id,
                f"{SECTION_DESCRIPTIONS[section]}\n\nیکی از گزینه‌ها را انتخاب کنید:",
                reply_markup=submenu_keyboard(section),
            )
            return

    if text:
        send_message(
            chat_id,
            "در فاز ۱ ورود متن آزاد پردازش نمی‌شود. از دکمه‌ها استفاده کنید یا /help را بفرستید.",
            reply_markup=main_menu_keyboard(),
        )


def action_section(action: str) -> str:
    callback = f"action:{action}"
    for section, rows in SUBMENU_ROWS.items():
        if any(target == callback for row in rows for _, target in row):
            return section
    return "support"


def expired_form_screen(chat_id: int | str, message_id: int | None) -> None:
    show_screen(
        chat_id,
        message_id,
        "⏳ این فرم منقضی یا انتخاب نامعتبر شده است. از منوی اصلی دوباره شروع کنید.",
        main_menu_keyboard(),
    )


def handle_member_callback(
    data: str,
    chat_id: int | str,
    user_id: int | str,
    message_id: int | None,
) -> bool:
    """رویدادهای ثبت‌نام، پروفایل و دعوت اعضا را مدیریت می‌کند."""
    if not data.startswith("member:"):
        return False
    repository = get_member_repository()
    session_key = form_session_key(chat_id, user_id)

    if data == "member:start":
        member = repository.get_member(user_id)
        if member:
            show_screen(
                chat_id,
                message_id,
                f"شما قبلاً ثبت‌نام کرده‌اید.\n\n{member_profile_text(member)}",
                build_inline_keyboard([[("✏️ ویرایش", "member:edit"), ("⬅️ بازگشت", "menu:account")]]),
            )
            return True
        show_screen(
            chat_id,
            message_id,
            "📝 ثبت‌نام عضویت\n\n"
            "در این مرحله فقط نام نمایشی، دانشگاه، نقش و ترجیحات عضویت ذخیره می‌شود.\n"
            "کد ملی، شماره دانشجویی، شماره تماس، اطلاعات بانکی و مدرک هویتی دریافت نمی‌شود.\n\n"
            "با شروع ثبت‌نام، ذخیره این اطلاعات حداقلی را می‌پذیرید.",
            build_inline_keyboard([
                [("✅ شروع ثبت‌نام", "member:consent")],
                [("⬅️ انصراف", "menu:account")],
            ]),
        )
        return True

    if data == "member:consent":
        if repository.get_member(user_id):
            show_screen(chat_id, message_id, "عضویت شما قبلاً ثبت شده است.", submenu_keyboard("account"))
            return True
        with MEMBER_LOCK:
            referred_by = PENDING_REFERRALS.pop(session_key, None)
            MEMBER_SESSIONS[session_key] = {
                "mode": "register",
                "step": "display_name",
                "answers": {},
                "referred_by": referred_by,
            }
        show_screen(
            chat_id,
            message_id,
            "مرحله ۱: یک نام نمایشی بین ۲ تا ۵۰ نویسه ارسال کنید.\n"
            "برای توقف می‌توانید /cancel را بفرستید.",
            build_inline_keyboard([[("❌ لغو", "member:cancel")]]),
        )
        return True

    if data.startswith("member:pick:"):
        parts = data.split(":", 3)
        if len(parts) != 4:
            return True
        _, _, field, value = parts
        with MEMBER_LOCK:
            state = MEMBER_SESSIONS.get(session_key)
            valid_values = {item_value for _, item_value in MEMBER_CHOICES.get(field, [])}
            if (
                not state
                or state["mode"] != "register"
                or state["step"] != field
                or value not in valid_values
            ):
                state = None
            else:
                state["answers"][field] = value
                next_steps = {"role": "participation", "participation": "notification", "notification": "confirm"}
                state["step"] = next_steps[field]
                snapshot = {**state, "answers": dict(state["answers"])}
        if state is None:
            expired_form_screen(chat_id, message_id)
            return True
        if snapshot["step"] == "confirm":
            show_screen(
                chat_id,
                message_id,
                member_summary_text(snapshot),
                build_inline_keyboard([
                    [("✅ ثبت عضویت", "member:confirm")],
                    [("⬅️ مرحله قبل", "member:back"), ("❌ لغو", "member:cancel")],
                ]),
            )
        else:
            prompt = "نوع مشارکت را انتخاب کنید:" if snapshot["step"] == "participation" else "تنظیم اعلان‌ها را انتخاب کنید:"
            show_screen(chat_id, message_id, prompt, member_choice_keyboard(snapshot["step"]))
        return True

    if data == "member:back":
        prompts = {
            "display_name": "نام نمایشی را دوباره ارسال کنید:",
            "university": "نام دانشگاه یا مرکز آموزشی را دوباره ارسال کنید:",
        }
        with MEMBER_LOCK:
            state = MEMBER_SESSIONS.get(session_key)
            if not state or state["mode"] != "register":
                state = None
            else:
                previous = {
                    "university": "display_name",
                    "role": "university",
                    "participation": "role",
                    "notification": "participation",
                    "confirm": "notification",
                }.get(state["step"])
                if previous:
                    state["step"] = previous
                    state["answers"].pop(previous, None)
                    snapshot = {**state, "answers": dict(state["answers"])}
                else:
                    snapshot = None
        if not state or not snapshot:
            expired_form_screen(chat_id, message_id)
        elif snapshot["step"] in prompts:
            show_screen(
                chat_id,
                message_id,
                prompts[snapshot["step"]],
                build_inline_keyboard([[("❌ لغو", "member:cancel")]]),
            )
        else:
            show_screen(
                chat_id,
                message_id,
                f"{MEMBER_FIELD_LABELS[snapshot['step']]} را دوباره انتخاب کنید:",
                member_choice_keyboard(snapshot["step"]),
            )
        return True

    if data == "member:confirm":
        with MEMBER_LOCK:
            state = MEMBER_SESSIONS.get(session_key)
            if not state or state["mode"] != "register" or state["step"] != "confirm":
                state = None
            else:
                state = {**state, "answers": dict(state["answers"])}
        if state is None:
            expired_form_screen(chat_id, message_id)
            return True
        if repository.get_member(user_id):
            with MEMBER_LOCK:
                MEMBER_SESSIONS.pop(session_key, None)
            show_screen(chat_id, message_id, "عضویت شما قبلاً ثبت شده است.", submenu_keyboard("account"))
            return True
        answers = state["answers"]
        member = repository.create_member(
            bale_user_id=user_id,
            chat_id=chat_id,
            display_name=answers["display_name"],
            university=answers["university"],
            role=answers["role"],
            participation=answers["participation"],
            notification=answers["notification"],
            referred_by=state.get("referred_by"),
        )
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        show_screen(
            chat_id,
            message_id,
            f"✅ ثبت‌نام انجام شد.\n\n{member_profile_text(member)}",
            build_inline_keyboard([[("🎁 کد دعوت من", "member:referral"), ("⬅️ حساب و عضویت", "menu:account")]]),
        )
        return True

    if data == "member:status":
        member = repository.get_member(user_id)
        if not member:
            show_screen(
                chat_id,
                message_id,
                "هنوز عضو نشده‌اید.",
                build_inline_keyboard([[("📝 ثبت‌نام", "member:start"), ("⬅️ بازگشت", "menu:account")]]),
            )
        else:
            show_screen(
                chat_id,
                message_id,
                member_profile_text(member),
                build_inline_keyboard([[("✏️ ویرایش", "member:edit"), ("⬅️ بازگشت", "menu:account")]]),
            )
        return True

    if data == "member:edit":
        if not repository.get_member(user_id):
            show_screen(chat_id, message_id, "برای ویرایش ابتدا ثبت‌نام کنید.", submenu_keyboard("account"))
            return True
        show_screen(
            chat_id,
            message_id,
            "کدام بخش پروفایل را می‌خواهید ویرایش کنید؟",
            build_inline_keyboard([
                [("نام نمایشی", "member:editfield:display_name"), ("دانشگاه", "member:editfield:university")],
                [("نقش", "member:editfield:role"), ("نوع مشارکت", "member:editfield:participation")],
                [("اعلان‌ها", "member:editfield:notification")],
                [("⬅️ بازگشت", "menu:account")],
            ]),
        )
        return True

    if data.startswith("member:editfield:"):
        field = data.removeprefix("member:editfield:")
        if field not in MEMBER_FIELD_LABELS or not repository.get_member(user_id):
            expired_form_screen(chat_id, message_id)
            return True
        if field in {"display_name", "university"}:
            with MEMBER_LOCK:
                MEMBER_SESSIONS[session_key] = {"mode": "edit", "step": f"edit_{field}", "answers": {}}
            show_screen(
                chat_id,
                message_id,
                f"مقدار جدید «{MEMBER_FIELD_LABELS[field]}» را ارسال کنید.\nبرای توقف /cancel را بفرستید.",
                build_inline_keyboard([[("❌ لغو", "member:cancel")]]),
            )
        else:
            show_screen(
                chat_id,
                message_id,
                f"مقدار جدید «{MEMBER_FIELD_LABELS[field]}» را انتخاب کنید:",
                member_choice_keyboard(field, prefix="member:update", back_callback="member:edit"),
            )
        return True

    if data.startswith("member:update:"):
        parts = data.split(":", 3)
        if len(parts) != 4:
            return True
        _, _, field, value = parts
        valid_values = {item_value for _, item_value in MEMBER_CHOICES.get(field, [])}
        if value not in valid_values:
            expired_form_screen(chat_id, message_id)
            return True
        member = repository.update_member(user_id, field, value)
        if member:
            show_screen(chat_id, message_id, f"✅ اطلاعات به‌روزرسانی شد.\n\n{member_profile_text(member)}", submenu_keyboard("account"))
        else:
            show_screen(chat_id, message_id, "عضویت پیدا نشد.", submenu_keyboard("account"))
        return True

    if data == "member:referral":
        member = repository.get_member(user_id)
        if not member:
            show_screen(chat_id, message_id, "برای دریافت کد دعوت ابتدا ثبت‌نام کنید.", submenu_keyboard("account"))
            return True
        referral_count = repository.count_referrals(member.referral_code)
        referral_link = f"https://ble.ir/{BOT_USERNAME}?start=ref_{member.referral_code}"
        show_screen(
            chat_id,
            message_id,
            "🎁 دعوت دوستان\n\n"
            f"کد دعوت: {member.referral_code}\n"
            f"لینک دعوت: {referral_link}\n"
            f"تعداد ثبت‌نام با کد شما: {referral_count}",
            build_inline_keyboard([[("⬅️ حساب و عضویت", "menu:account")]]),
        )
        return True

    if data == "member:cancel":
        with MEMBER_LOCK:
            MEMBER_SESSIONS.pop(session_key, None)
        show_screen(chat_id, message_id, "عملیات عضویت لغو شد.", submenu_keyboard("account"))
        return True

    return False


def handle_callback_query(query: dict):
    """مدیریت منوها و فرم‌های شیشه‌ای فاز یک."""
    callback_id = str(query.get("id") or query.get("callback_query_id") or "")
    data = str(query.get("data") or "")
    message = query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    user_id = (query.get("from") or {}).get("id")
    if not chat_id:
        answer_callback_query(callback_id, "امکان تشخیص گفتگو وجود ندارد.")
        return

    # پاسخ به callback برای خروج دکمه از حالت انتظار الزامی است.
    answer_callback_query(callback_id)
    session_key = form_session_key(chat_id, user_id)

    if data == "menu:main":
        with FORM_LOCK:
            FORM_SESSIONS.pop(session_key, None)
        show_screen(chat_id, message_id, "🏠 منوی اصلی\nیک بخش را انتخاب کنید:", main_menu_keyboard())
        return

    if data.startswith("menu:"):
        section = data.removeprefix("menu:")
        if section in SECTION_DESCRIPTIONS:
            with FORM_LOCK:
                FORM_SESSIONS.pop(session_key, None)
            show_screen(
                chat_id,
                message_id,
                f"{SECTION_DESCRIPTIONS[section]}\n\nیکی از گزینه‌ها را انتخاب کنید:",
                submenu_keyboard(section),
            )
            return

    if handle_member_callback(data, chat_id, user_id or chat_id, message_id):
        return

    if data == "phase4:my_enterprises":
        interests = get_member_repository().list_enterprise_interests(user_id or chat_id)
        if interests:
            lines = [
                f"• {ENTERPRISE_IDEA_LABELS.get(item['idea_type'], item['idea_type'])} — "
                f"{ENTERPRISE_CONTRIBUTION_LABELS.get(item['contribution'], item['contribution'])}"
                for item in interests
            ]
            text = "ایده‌ها و علاقه‌مندی‌های شما برای بررسی کسب‌وکار اجتماعی:\n\n" + "\n".join(lines)
        else:
            text = "هنوز علاقه‌مندی‌ای برای ایده‌های کسب‌وکار اجتماعی ثبت نکرده‌اید."
        show_screen(
            chat_id,
            message_id,
            text,
            build_inline_keyboard([[ ("⬅️ بازگشت", "menu:network"), ("🏠 منوی اصلی", "menu:main") ]]),
        )
        return

    if data in {"phase3:my_workshops", "phase3:my_branches"}:
        repository = get_member_repository()
        if data == "phase3:my_workshops":
            interests = repository.list_workshop_interests(user_id or chat_id)
            if interests:
                lines = [
                    f"• {WORKSHOP_TOPIC_LABELS.get(item['topic'], item['topic'])} — "
                    f"{ATTENDANCE_LABELS.get(item['attendance_mode'], item['attendance_mode'])}"
                    for item in interests
                ]
                text = "📋 علاقه‌مندی‌های کارگاهی شما:\n\n" + "\n".join(lines)
            else:
                text = "هنوز علاقه‌مندی کارگاهی ثبت نکرده‌اید."
            section = "learning"
        else:
            interests = repository.list_branch_interests(user_id or chat_id)
            if interests:
                lines = [
                    f"• {item['university']} — "
                    f"{BRANCH_ROLE_LABELS.get(item['team_role'], item['team_role'])}، "
                    f"{AVAILABILITY_LABELS.get(item['availability'], item['availability'])} "
                    f"({item['status']})"
                    for item in interests
                ]
                text = "📋 اعلام آمادگی‌های شما برای توسعهٔ شعبه:\n\n" + "\n".join(lines)
            else:
                text = "هنوز اعلام آمادگی برای شعبهٔ دانشگاهی ثبت نکرده‌اید."
            section = "network"
        show_screen(
            chat_id,
            message_id,
            text,
            build_inline_keyboard([[ ("⬅️ بازگشت", f"menu:{section}"), ("🏠 منوی اصلی", "menu:main") ]]),
        )
        return

    if data.startswith("action:"):
        action = data.removeprefix("action:")
        section = action_section(action)
        message_text = ACTION_MESSAGES.get(action, "این قابلیت در فازهای عملیاتی فعال خواهد شد.")
        keyboard = build_inline_keyboard([
            [("⬅️ بازگشت", f"menu:{section}"), ("🏠 منوی اصلی", "menu:main")]
        ])
        phase_note = "ℹ️ اطلاعات و برنامهٔ فاز ۳" if action in PHASE3_ACTIONS else "ℹ️ پیش‌نمایش فاز ۱"
        if action in PHASE4_ACTIONS:
            phase_note = "ℹ️ اطلاعات و برنامهٔ فاز ۴"
        show_screen(chat_id, message_id, f"{message_text}\n\n{phase_note}", keyboard)
        return

    if data.startswith("form:start:"):
        flow = data.removeprefix("form:start:")
        if flow not in FORM_SPECS:
            expired_form_screen(chat_id, message_id)
            return
        spec = FORM_SPECS[flow]
        if spec.get("requires_member") and not get_member_repository().get_member(user_id or chat_id):
            show_screen(
                chat_id,
                message_id,
                "برای اعلام آمادگی شعبه، ابتدا پروفایل عضویت و دانشگاه خود را ثبت کنید.\n"
                "اطلاعات تماس یا مدرک هویتی لازم نیست.",
                build_inline_keyboard([
                    [("📝 شروع عضویت", "member:start")],
                    [("⬅️ بازگشت", "menu:network")],
                ]),
            )
            return
        with FORM_LOCK:
            state = {"flow": flow, "step": 0, "answers": {}}
            FORM_SESSIONS[session_key] = state
            text, keyboard = form_screen(state)
        show_screen(chat_id, message_id, text, keyboard)
        return

    if data.startswith("form:pick:"):
        parts = data.split(":", 4)
        if len(parts) != 5:
            expired_form_screen(chat_id, message_id)
            return
        _, _, flow, step_key, value = parts
        with FORM_LOCK:
            state = FORM_SESSIONS.get(session_key)
            if not state or state["flow"] != flow:
                state = None
            else:
                spec = FORM_SPECS[flow]
                step_index = state["step"]
                if step_index >= len(spec["steps"]):
                    state = None
                else:
                    expected_key, _, options = spec["steps"][step_index]
                    valid_values = {option_value for _, option_value in options}
                    if step_key != expected_key or value not in valid_values:
                        state = None
                    else:
                        state["answers"][step_key] = value
                        state["step"] += 1
                        text, keyboard = form_screen(state)
        if state is None:
            expired_form_screen(chat_id, message_id)
        else:
            show_screen(chat_id, message_id, text, keyboard)
        return

    if data == "form:back":
        with FORM_LOCK:
            state = FORM_SESSIONS.get(session_key)
            if state:
                state["step"] = max(0, state["step"] - 1)
                previous_key = FORM_SPECS[state["flow"]]["steps"][state["step"]][0]
                state["answers"].pop(previous_key, None)
                text, keyboard = form_screen(state)
        if state:
            show_screen(chat_id, message_id, text, keyboard)
        else:
            expired_form_screen(chat_id, message_id)
        return

    if data == "form:cancel":
        with FORM_LOCK:
            state = FORM_SESSIONS.pop(session_key, None)
        section = FORM_SPECS[state["flow"]]["section"] if state else "support"
        show_screen(
            chat_id,
            message_id,
            f"فرم آزمایشی لغو شد.\n\n{SECTION_DESCRIPTIONS[section]}",
            submenu_keyboard(section),
        )
        return

    if data == "form:confirm":
        with FORM_LOCK:
            state = FORM_SESSIONS.pop(session_key, None)
        if not state or state["step"] != len(FORM_SPECS[state["flow"]]["steps"]):
            expired_form_screen(chat_id, message_id)
            return
        spec = FORM_SPECS[state["flow"]]
        section = spec["section"]
        user_key = user_id or chat_id
        if spec.get("persist") == "workshop_interest":
            answers = state["answers"]
            get_member_repository().save_workshop_interest(
                bale_user_id=user_key,
                chat_id=chat_id,
                topic=answers["topic"],
                attendance_mode=answers["attendance"],
            )
            result_text = (
                "✅ علاقه‌مندی کارگاهی شما ثبت شد.\n"
                "این ثبت به معنی پذیرش نهایی یا رزرو قطعی نیست؛ زمان، ظرفیت و شرایط بعداً اعلام می‌شود.\n"
                "هیچ وجهی دریافت نشده است."
            )
        elif spec.get("persist") == "branch_interest":
            repository = get_member_repository()
            member = repository.get_member(user_key)
            if not member:
                expired_form_screen(chat_id, message_id)
                return
            answers = state["answers"]
            repository.save_branch_interest(
                bale_user_id=user_key,
                chat_id=chat_id,
                university=member.university,
                team_role=answers["team_role"],
                availability=answers["availability"],
            )
            result_text = (
                "✅ اعلام آمادگی شما برای توسعهٔ شعبه ثبت شد.\n"
                f"دانشگاه ثبت‌شده: {member.university}\n"
                "این اعلام علاقه‌مندی است و به‌تنهایی به معنی ایجاد یا تأیید شعبه نیست."
            )
        elif spec.get("persist") == "enterprise_interest":
            answers = state["answers"]
            get_member_repository().save_enterprise_interest(
                bale_user_id=user_key,
                chat_id=chat_id,
                idea_type=answers["idea_type"],
                contribution=answers["contribution"],
            )
            result_text = (
                "✅ علاقه‌مندی شما برای بررسی ایدهٔ کسب‌وکار اجتماعی ثبت شد.\n"
                "این ثبت به معنی تصویب طرح، ایجاد شرکت، تعهد مالی یا تضمین درآمد نیست؛ تصمیم‌گیری پس از بررسی مسئولان انجام می‌شود."
            )
        else:
            result_text = (
                "✅ پیش‌نمایش فرم با موفقیت پایان یافت.\n"
                "هیچ اطلاعاتی ذخیره و هیچ پرداختی انجام نشد."
            )
        show_screen(
            chat_id,
            message_id,
            result_text,
            build_inline_keyboard([
                [("⬅️ بازگشت به بخش", f"menu:{section}"), ("🏠 منوی اصلی", "menu:main")]
            ]),
        )
        return

    show_screen(chat_id, message_id, "گزینه شناخته نشد؛ به منوی اصلی برگشتیم.", main_menu_keyboard())


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
            elif "callback_query" in data:
                executor.submit(handle_callback_query, data["callback_query"])
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
                        elif "callback_query" in update:
                            executor.submit(handle_callback_query, update["callback_query"])
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
