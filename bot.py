"""
PDFX AI - Telegram bot v1.1
Turns raw text or existing PDFs into professionally redesigned documents.
"""

import asyncio
import itertools
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
from pdf_processor import extract_pdf_content, format_content_for_ai

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
MAX_CHARS = 25000  # Increased for PDF content

NEW_PDF_BTN = "📄 إنشاء PDF جديد"

WELCOME_TEXT = (
    "👋 *أهلًا بك في PDFX AI*\n\n"
    "أنا *مهندس مستندات يعمل بالذكاء الاصطناعي*.\n\n"
    "✨ *ماذا يمكنني أن أفعل؟*\n"
    "1️⃣ **تحويل النصوص**: أرسل أي نص وسأحوله لمستند احترافي.\n"
    "2️⃣ **إعادة تصميم PDF**: أرسل لي أي ملف PDF قديم، وسأعيد بناءه بتصميم عصري مع الحفاظ على المحتوى.\n\n"
    "وسأقوم بـ:\n"
    "✅ تحليل الهيكل وتحديد نوع المستند\n"
    "✅ استخراج الصور والجداول وإعادة رسمها باحترافية\n"
    "✅ تنسيق شامل (غلاف، فهرس، ألوان متناسقة)\n\n"
    "أرسل نصك أو ملف PDF الآن للبدء 👇"
)

HELP_TEXT = (
    "ℹ️ *كيفية الاستخدام*\n\n"
    "• **للنصوص**: اكتب أو الصق النص مباشرة.\n"
    "• **لملفات PDF**: أرسل الملف كـ Document وسأقوم بإعادة تصميمه.\n"
    "• **للهوية البصرية**: (قريبًا) أرسل شعارك ليتم دمجه.\n\n"
    f"الحد الأقصى للمحتوى: {MAX_CHARS} حرف."
)

_ANALYZE_STAGES = [
    "🧠 جاري تحليل المحتوى...",
    "📖 جاري قراءة النص وفهم سياقه...",
    "✍️ جاري تصحيح الصياغة وتنظيم الفقرات...",
    "🔎 جاري تحديد نوع المستند وأسلوبه...",
    "⏳ الموديل مشغول، لسه بنحلل... شكرًا لصبرك.",
]

_REDESIGN_STAGES = [
    "📥 جاري معالجة ملف الـ PDF...",
    "🔍 جاري استخراج النصوص والجداول...",
    "🖼️ جاري استخراج الصور وتحسين جودتها...",
    "🧠 جاري إعادة بناء هيكل المستند بالذكاء الاصطناعي...",
]

_DESIGN_STAGES = [
    "🎨 جاري تصميم المستند وإنشاء الـ PDF...",
    "🖌️ جاري اختيار الألوان والتخطيط المناسب للمحتوى...",
    "📐 جاري بناء الغلاف والفهرس...",
    "📄 جاري تجميع الصفحات النهائية...",
]

async def _keepalive(status_msg, chat_id, bot, stages, interval=4.0):
    t0 = time.time()
    cycle = itertools.cycle(stages)
    next(cycle)
    try:
        while True:
            await asyncio.sleep(interval)
            elapsed = int(time.time() - t0)
            line = next(cycle)
            try:
                await status_msg.edit_text(f"{line}\n⏱️ {elapsed} ثانية...")
            except Exception: pass
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception: pass
    except asyncio.CancelledError: pass

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if len(text) < MIN_CHARS:
        await update.message.reply_text("✏️ النص قصير جدًا.")
        return
    await handle_processing(update, context, text, is_pdf=False)

async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("❌ عذراً، أقبل ملفات PDF فقط لإعادة التصميم.")
        return

    status_msg = await update.message.reply_text(_REDESIGN_STAGES[0])
    chat_id = update.effective_chat.id
    
    keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _REDESIGN_STAGES))
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = await doc.get_file()
            pdf_path = os.path.join(tmpdir, "input.pdf")
            await pdf_file.download_to_drive(pdf_path)
            
            content = await _run_blocking(extract_pdf_content, pdf_path, tmpdir)
            formatted_text = format_content_for_ai(content)
            
            keepalive_task.cancel()
            await handle_processing(update, context, formatted_text, is_pdf=True, status_msg=status_msg)
            
    except Exception as e:
        keepalive_task.cancel()
        log.error("PDF processing error: %s", traceback.format_exc())
        await status_msg.edit_text("❌ حدث خطأ أثناء معالجة ملف الـ PDF.")

async def handle_processing(update, context, text, is_pdf=False, status_msg=None):
    chat_id = update.effective_chat.id
    t0 = time.time()
    
    if not status_msg:
        status_msg = await update.message.reply_text(_ANALYZE_STAGES[0])
    
    keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _ANALYZE_STAGES))
    
    try:
        system_hint = "REDESIGN_MODE: Keep all original content, structure, and tables." if is_pdf else ""
        plan = await context.application.create_task(
            _run_blocking(analyze_text, text, 120.0, system_hint)
        )
        
        doc_type_ar = {
            "report": "تقرير", "research": "بحث", "article": "مقال", "book": "كتاب",
            "summary": "ملخص", "memo": "مذكرة", "cv": "سيرة ذاتية", "invoice": "فاتورة",
            "letter": "خطاب رسمي", "contract": "عقد", "business_plan": "خطة عمل",
            "proposal": "عرض مشروع", "general": "مستند",
        }.get(plan.get("doc_type", "general"), "مستند")

        await status_msg.edit_text(
            f"✅ تم التحليل — نوع المستند: *{doc_type_ar}*\n{_DESIGN_STAGES[0]}",
            parse_mode=ParseMode.MARKDOWN,
        )
        
        keepalive_task.cancel()
        keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _DESIGN_STAGES))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.pdf")
            await context.application.create_task(_run_blocking(render_pdf, plan, out_path))
            
            elapsed = time.time() - t0
            filename = f"Redesigned_{plan.get('title', 'document')[:50]}.pdf"
            
            with open(out_path, "rb") as f:
                await update.message.reply_document(
                    document=f, filename=filename,
                    caption=f"✅ تم {'إعادة تصميم' if is_pdf else 'إنشاء'} المستند بنجاح في {elapsed:.1f} ثانية."
                )
        await status_msg.delete()
    except Exception as e:
        log.error("Processing failure: %s", traceback.format_exc())
        if status_msg:
            await status_msg.edit_text(f"❌ حدث خطأ أثناء المعالجة: {str(e)[:100]}")
    finally:
        keepalive_task.cancel()

async def _run_blocking(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)

def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.Document.PDF, on_document))
    return app

if __name__ == "__main__":
    application = build_app()
    application.run_polling()
