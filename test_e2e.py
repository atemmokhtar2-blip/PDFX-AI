import sys
import time
from analyzer import analyze_text, AnalyzerError
from renderer import render_pdf

samples = {
    "invoice_ar": """فاتورة لشركة النور للتجارة. رقم الفاتورة INV-2026-045. التاريخ 15 يوليو 2026.
البنود: 10 قطع من منتج أ بسعر 50 جنيه للقطعة، 5 قطع من منتج ب بسعر 120 جنيه للقطعة، خدمة تركيب بسعر 300 جنيه.
الإجمالي قبل الضريبة 1700 جنيه، ضريبة القيمة المضافة 14%، الإجمالي النهائي 1938 جنيه.
طريقة الدفع: تحويل بنكي. تاريخ الاستحقاق: 30 يوليو 2026.""",
    "letter_en": """Dear Mr. Johnson, I would like to formally request a two week extension for the project deadline due to unforeseen delays in the supply chain. We have completed 80 percent of the deliverables and expect to finish the remainder by August 5th. Thank you for your understanding. Best regards, Sarah Ahmed, Project Manager""",
    "article_mixed": """The rise of AI agents في عالم البرمجيات أصبح ظاهرة لا يمكن تجاهلها. Companies like OpenAI and Anthropic تتنافس على تطوير نماذج أكثر ذكاءً. هذا المقال يستعرض التطورات الأخيرة in agentic AI systems وتأثيرها على سوق العمل."""
}

for name, text in samples.items():
    print(f"=== {name} ===")
    t0 = time.time()
    try:
        plan = analyze_text(text)
    except AnalyzerError as e:
        print("ANALYZE FAIL:", e)
        continue
    print("doc_type:", plan.get("doc_type"), "| lang:", plan.get("language"), "| dir:", plan.get("direction"))
    print("title:", plan.get("title"))
    out = f"e2e_{name}.pdf"
    try:
        render_pdf(plan, out)
        print("rendered:", out, f"({time.time()-t0:.1f}s)")
    except Exception as e:
        print("RENDER FAIL:", e)
    print()
