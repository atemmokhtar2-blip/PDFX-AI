"""
243	PDFX AI - Telegram bot v1.1
244	Turns raw text or existing PDFs into professionally redesigned documents.
245	"""
246	
247	import asyncio
248	import itertools
249	import logging
250	import os
251	import tempfile
252	import time
253	import traceback
254	
255	from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
256	from telegram.constants import ChatAction, ParseMode
257	from telegram.ext import (
258	    Application,
259	    CallbackQueryHandler,
260	    CommandHandler,
261	    ContextTypes,
262	    MessageHandler,
263	    filters,
264	)
265	
266	from analyzer import AnalyzerError, analyze_text
267	from renderer import render_pdf
268	from pdf_processor import extract_pdf_content, format_content_for_ai
269	
270	logging.basicConfig(
271	    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
272	    level=logging.INFO,
273	)
274	logging.getLogger("httpx").setLevel(logging.WARNING)
275	logging.getLogger("weasyprint").setLevel(logging.ERROR)
276	logging.getLogger("fontTools").setLevel(logging.ERROR)
277	log = logging.getLogger("pdfx-ai")
278	
279	BOT_TOKEN = os.environ.get("PDFX_BOT_TOKEN")
280	if not BOT_TOKEN:
281	    raise SystemExit("PDFX_BOT_TOKEN environment variable is required")
282	
283	MIN_CHARS = 8
284	MAX_CHARS = 25000  # Increased for PDF content
285	
286	NEW_PDF_BTN = "📄 إنشاء PDF جديد"
287	
288	WELCOME_TEXT = (
289	    "👋 *أهلًا بك في PDFX AI*\n\n"
290	    "أنا *مهندس مستندات يعمل بالذكاء الاصطناعي*.\n\n"
291	    "✨ *ماذا يمكنني أن أفعل؟*\n"
292	    "1️⃣ **تحويل النصوص**: أرسل أي نص وسأحوله لمستند احترافي.\n"
293	    "2️⃣ **إعادة تصميم PDF**: أرسل لي أي ملف PDF قديم، وسأعيد بناءه بتصميم عصري مع الحفاظ على المحتوى.\n\n"
294	    "وسأقوم بـ:\n"
295	    "✅ تحليل الهيكل وتحديد نوع المستند\n"
296	    "✅ استخراج الصور والجداول وإعادة رسمها باحترافية\n"
297	    "✅ تنسيق شامل (غلاف، فهرس، ألوان متناسقة)\n\n"
298	    "أرسل نصك أو ملف PDF الآن للبدء 👇"
299	)
300	
301	HELP_TEXT = (
302	    "ℹ️ *كيفية الاستخدام*\n\n"
303	    "• **للنصوص**: اكتب أو الصق النص مباشرة.\n"
304	    "• **لملفات PDF**: أرسل الملف كـ Document وسأقوم بإعادة تصميمه.\n"
305	    "• **للهوية البصرية**: (قريبًا) أرسل شعارك ليتم دمجه.\n\n"
306	    f"الحد الأقصى للمحتوى: {MAX_CHARS} حرف."
307	)
308	
309	_ANALYZE_STAGES = [
310	    "🧠 جاري تحليل المحتوى...",
311	    "📖 جاري قراءة النص وفهم سياقه...",
312	    "✍️ جاري تصحيح الصياغة وتنظيم الفقرات...",
313	    "🔎 جاري تحديد نوع المستند وأسلوبه...",
314	    "⏳ الموديل مشغول، لسه بنحلل... شكرًا لصبرك.",
315	]
316	
317	_REDESIGN_STAGES = [
318	    "📥 جاري معالجة ملف الـ PDF...",
319	    "🔍 جاري استخراج النصوص والجداول...",
320	    "🖼️ جاري استخراج الصور وتحسين جودتها...",
321	    "🧠 جاري إعادة بناء هيكل المستند بالذكاء الاصطناعي...",
322	]
323	
324	_DESIGN_STAGES = [
325	    "🎨 جاري تصميم المستند وإنشاء الـ PDF...",
326	    "🖌️ جاري اختيار الألوان والتخطيط المناسب للمحتوى...",
327	    "📐 جاري بناء الغلاف والفهرس...",
328	    "📄 جاري تجميع الصفحات النهائية...",
329	]
330	
331	async def _keepalive(status_msg, chat_id, bot, stages, interval=6.0):
332	    t0 = time.time()
333	    cycle = itertools.cycle(stages)
334	    next(cycle)
335	    try:
336	        while True:
337	            await asyncio.sleep(interval)
338	            elapsed = int(time.time() - t0)
339	            line = next(cycle)
340	            try:
341	                await status_msg.edit_text(f"{line}\n⏱️ {elapsed} ثانية...")
342	            except Exception: pass
343	            try:
344	                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
345	            except Exception: pass
346	    except asyncio.CancelledError: pass
347	
348	async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
349	    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN)
350	
351	async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
352	    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)
353	
354	async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
355	    text = (update.message.text or "").strip()
356	    if len(text) < MIN_CHARS:
357	        await update.message.reply_text("✏️ النص قصير جدًا.")
358	        return
359	    await handle_processing(update, context, text, is_pdf=False)
360	
361	async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
362	    doc = update.message.document
363	    if doc.mime_type != "application/pdf":
364	        await update.message.reply_text("❌ عذراً، أقبل ملفات PDF فقط لإعادة التصميم.")
365	        return
366	
367	    status_msg = await update.message.reply_text(_REDESIGN_STAGES[0])
368	    chat_id = update.effective_chat.id
369	    
370	    keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _REDESIGN_STAGES))
371	    
372	    try:
373	        with tempfile.TemporaryDirectory() as tmpdir:
374	            pdf_file = await doc.get_file()
375	            pdf_path = os.path.join(tmpdir, "input.pdf")
376	            await pdf_file.download_to_drive(pdf_path)
377	            
378	            content = await _run_blocking(extract_pdf_content, pdf_path, tmpdir)
379	            formatted_text = format_content_for_ai(content)
380	            
381	            keepalive_task.cancel()
382	            await handle_processing(update, context, formatted_text, is_pdf=True, status_msg=status_msg)
383	            
384	    except Exception as e:
385	        keepalive_task.cancel()
386	        log.error("PDF processing error: %s", traceback.format_exc())
387	        await status_msg.edit_text("❌ حدث خطأ أثناء معالجة ملف الـ PDF.")
388	
389	async def handle_processing(update, context, text, is_pdf=False, status_msg=None):
390	    chat_id = update.effective_chat.id
391	    t0 = time.time()
392	    
393	    if not status_msg:
394	        status_msg = await update.message.reply_text(_ANALYZE_STAGES[0])
395	    
396	    keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _ANALYZE_STAGES))
397	    
398	    try:
399	        system_hint = "REDESIGN_MODE: Keep all original content, structure, and tables." if is_pdf else ""
400	        plan = await context.application.create_task(_run_blocking(analyze_text, text, system_hint))
401	        
402	        doc_type_ar = {
403	            "report": "تقرير", "research": "بحث", "article": "مقال", "book": "كتاب",
404	            "summary": "ملخص", "memo": "مذكرة", "cv": "سيرة ذاتية", "invoice": "فاتورة",
405	            "letter": "خطاب رسمي", "contract": "عقد", "business_plan": "خطة عمل",
406	            "proposal": "عرض مشروع", "general": "مستند",
407	        }.get(plan.get("doc_type", "general"), "مستند")
408	
409	        await status_msg.edit_text(
410	            f"✅ تم التحليل — نوع المستند: *{doc_type_ar}*\n{_DESIGN_STAGES[0]}",
411	            parse_mode=ParseMode.MARKDOWN,
412	        )
413	        
414	        keepalive_task.cancel()
415	        keepalive_task = asyncio.create_task(_keepalive(status_msg, chat_id, context.bot, _DESIGN_STAGES))
416	        
417	        with tempfile.TemporaryDirectory() as tmpdir:
418	            out_path = os.path.join(tmpdir, "output.pdf")
419	            await context.application.create_task(_run_blocking(render_pdf, plan, out_path))
420	            
421	            elapsed = time.time() - t0
422	            filename = f"Redesigned_{plan.get('title', 'document')[:50]}.pdf"
423	            
424	            with open(out_path, "rb") as f:
425	                await update.message.reply_document(
426	                    document=f, filename=filename,
427	                    caption=f"✅ تم {'إعادة تصميم' if is_pdf else 'إنشاء'} المستند بنجاح في {elapsed:.1f} ثانية."
428	                )
429	        await status_msg.delete()
430	    except Exception as e:
431	        log.error("Processing failure: %s", traceback.format_exc())
432	        await status_msg.edit_text("❌ حدث خطأ أثناء المعالجة.")
433	    finally:
434	        keepalive_task.cancel()
435	
436	async def _run_blocking(fn, *args):
437	    loop = asyncio.get_running_loop()
438	    return await loop.run_in_executor(None, fn, *args)
439	
440	def build_app() -> Application:
441	    app = Application.builder().token(BOT_TOKEN).build()
442	    app.add_handler(CommandHandler("start", cmd_start))
443	    app.add_handler(CommandHandler("help", cmd_help))
444	    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
445	    app.add_handler(MessageHandler(filters.Document.PDF, on_document))
446	    return app
447	
448	if __name__ == "__main__":
449	    application = build_app()
450	    application.run_polling()
451	
