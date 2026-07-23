"""
PDFX AI - Telegram bot v1.0
Turns raw text into a professionally designed PDF document using AI
analysis (Kilo Gateway) + WeasyPrint rendering.
"""

import logging
import os
import tempfile
import time
import traceback

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from analyzer import AnalyzerError, analyze_text
from renderer import render_pdf

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.ERROR)
logging.getLogger("fontTools").setLevel(logging.ERROR)
log = logging.getLogger("pdfx-ai")

BOT_TOKEN = os.environ.get("PDFX_BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("PDFX_BOT_TOKEN environment variable is required")

MIN_CHARS = 8
MAX_CHARS = 12000

NEW_PDF_BTN = "📄 إنشاء PDF جديد"

WELCOME_TEXT = (
    "👋 *أهلًا بك في PDFX AI*\n\n"
    "لست مجرد محول نصوص إلى PDF — أنا *مصمم مستندات يعمل بالذكاء الاصطناعي*.\n\n"
    "📝 أرسل لي أي نص (تقرير، سيرة ذاتية، مقال، فاتورة، خطاب، أو أي مستند آخر)،\n"
    "وسأقوم بـ:\n"
    "1️⃣ تحليل المحتوى وتحديد نوع المستند\n"
    "2️⃣ تصحيح الأخطاء وتحسين الصياغة\n"
    "3️⃣ تنسيقه بتصميم احترافي (غلاف، فهرس، جداول...)\n"
    "4️⃣ إرسال ملف PDF جاهز للطباعة أو المشاركة\n\n"
    "🌐 أدعم العربية والإنجليزية والمزيج بينهما.\n\n"
    "أرسل نصك الآن للبدء 👇"
)

HELP_TEXT = (
    "ℹ️ *كيفية الاستخدام*\n\n"
    "فقط أرسل أي نص وسأحوّله إلى مستند PDF منسق باحتراف.\n"
    "لا حاجة لتحديد نوع المستند أو التنسيق — الذكاء الاصطناعي يتولى ذلك تلقائيًا.\n\n"
    f"الحد الأدنى: {MIN_CHARS} حروف، الحد الأقصى: {MAX_CHARS} حرف تقريبًا."
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(NEW_PDF_BTN, callback_data="new_pdf")]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def on_new_pdf_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📝 أرسل النص الذي تريد تحويله إلى PDF الآن.", reply_markup=None
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id

    if len(text) < MIN_CHARS:
        await update.message.reply_text(
            "✏️ النص قصير جدًا. أرسل نصًا أطول لأتمكن من تصميم مستند مناسب له."
        )
        return
    if len(text) > MAX_CHARS:
        await update.message.reply_text(
            f"⚠️ النص طويل جدًا (الحد الأقصى ~{MAX_CHARS} حرف). "
            "من فضلك أرسله على أجزاء أو قصّره."
        )
        return

    status_msg = await update.message.reply_text("🧠 جاري تحليل المحتوى...")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    t0 = time.time()
    try:
        plan = await context.application.create_task(
            _run_blocking(analyze_text, text)
        )
    except AnalyzerError as e:
        log.warning("Analyzer error: %s", e)
        await status_msg.edit_text(
            "❌ حدث خطأ أثناء تحليل النص بالذكاء الاصطناعي. حاول مرة أخرى بعد قليل."
        )
        return
    except Exception:
        log.error("Unexpected analyzer failure:\n%s", traceback.format_exc())
        await status_msg.edit_text("❌ حدث خطأ غير متوقع أثناء التحليل. حاول مرة أخرى.")
        return

    doc_type_ar = {
        "report": "تقرير", "research": "بحث", "article": "مقال", "book": "كتاب",
        "summary": "ملخص", "memo": "مذكرة", "cv": "سيرة ذاتية", "invoice": "فاتورة",
        "letter": "خطاب رسمي", "contract": "عقد", "business_plan": "خطة عمل",
        "proposal": "عرض مشروع", "general": "مستند",
    }.get(plan.get("doc_type", "general"), "مستند")

    await status_msg.edit_text(
        f"✅ تم التحليل — نوع المستند: *{doc_type_ar}*\n🎨 جاري تصميم المستند وإنشاء الـ PDF...",
        parse_mode=ParseMode.MARKDOWN,
    )
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "document.pdf")
            await context.application.create_task(_run_blocking(render_pdf, plan, out_path))

            elapsed = time.time() - t0
            safe_title = "".join(
                c for c in plan.get("title", "document") if c.isalnum() or c in " _-"
            ).strip() or "document"
            filename = f"{safe_title[:60]}.pdf"

            with open(out_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=f"✅ تم إنشاء المستند بنجاح في {elapsed:.1f} ثانية.\n"
                    f"📄 النوع: {doc_type_ar}",
                )
        await status_msg.delete()
    except Exception:
        log.error("Rendering failure:\n%s", traceback.format_exc())
        await status_msg.edit_text(
            "❌ حدث خطأ أثناء إنشاء ملف PDF. حاول مرة أخرى أو راجع النص المرسل."
        )


async def _run_blocking(fn, *args):
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error: %s", context.error, exc_info=context.error)


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_new_pdf_button, pattern="^new_pdf$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


if __name__ == "__main__":
    log.info("Starting PDFX AI bot...")
    application = build_app()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
