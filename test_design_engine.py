"""Manual smoke test for the new Design Intelligence Engine + smart boxes.
Renders several varied plans directly (no AI call) to check that:
  - different tones get different palettes/covers
  - repeated calls with the SAME plan still produce different designs
  - smart boxes (:::definition, :::warning, :::steps, :::stats, :::compare)
    render without crashing, in both RTL and LTR
"""
from renderer import render_pdf

ar_research = {
    "doc_type": "research",
    "tone": "medical",
    "language": "ar",
    "direction": "rtl",
    "title": "أثر النوم على الذاكرة قصيرة المدى",
    "subtitle": "دراسة تحليلية",
    "author": "د. سارة حسن",
    "date": "يوليو 2026",
    "needs_cover": True,
    "needs_toc": True,
    "content_markdown": """## المقدمة
النوم عنصر أساسي في تثبيت الذكريات قصيرة المدى وتحويلها لذكريات طويلة المدى.

:::definition الذاكرة قصيرة المدى
هي القدرة على الاحتفاظ بكمية محدودة من المعلومات لفترة قصيرة، تتراوح بين ثوانٍ ودقائق قليلة.
:::

## النتائج

:::stats
- 68%: تحسن في الاستدعاء بعد نوم كافٍ
- 3.2 ساعة: متوسط نوم المشاركين الأقل أداءً
- 120: عدد المشاركين في الدراسة
:::

:::warning
قلة النوم المزمنة قد تؤثر سلبًا على القدرات المعرفية طويلة المدى، وليس فقط الذاكرة قصيرة المدى.
:::

## خطوات إجراء التجربة

:::steps
- تجنيد المشاركين وتقسيمهم لمجموعتين
- قياس الذاكرة قبل فترة النوم
- تطبيق فترة نوم منضبطة لكل مجموعة
- إعادة قياس الذاكرة وتحليل الفروق
:::

## مقارنة بين المجموعتين

:::compare
| المعيار | مجموعة النوم الكافي | مجموعة قلة النوم |
| --- | --- | --- |
| متوسط الاستدعاء | 87% | 54% |
| زمن الاستجابة | سريع | متأخر |
:::

## خاتمة

:::highlight
تؤكد النتائج أن النوم الكافي عامل حاسم في تعزيز الذاكرة قصيرة المدى.
:::

> "النوم ليس رفاهية، بل ضرورة معرفية." — أحد المشاركين في الدراسة
""",
}

en_childrens_book = {
    "doc_type": "book",
    "tone": "playful",
    "language": "en",
    "direction": "ltr",
    "title": "Milo and the Missing Star",
    "subtitle": "A bedtime story",
    "author": None,
    "date": None,
    "needs_cover": True,
    "needs_toc": False,
    "content_markdown": """## Chapter 1: The Night Sky

Milo loved counting stars every night before bed.

:::note
Milo's favorite star was the brightest one, right above his window.
:::

One night, the brightest star was gone!

:::highlight
Milo decided he would find the missing star, no matter what.
:::

:::steps
- Milo asked the moon for help
- The moon pointed him toward the clouds
- Milo climbed a beam of moonlight
- He found the star hiding behind a cloud
:::

## Chapter 2: Coming Home

Milo brought the star back to the sky, and everyone cheered.
""",
}

en_contract = {
    "doc_type": "contract",
    "tone": "legal",
    "language": "en",
    "direction": "ltr",
    "title": "Service Agreement",
    "subtitle": None,
    "author": None,
    "date": "July 2026",
    "needs_cover": True,
    "needs_toc": False,
    "content_markdown": """## Parties

This agreement is entered into between Party A and Party B.

:::definition Force Majeure
An unforeseeable event beyond the control of either party that prevents fulfillment of contractual obligations.
:::

:::warning
Failure to deliver by the agreed date may result in termination of this agreement.
:::

## Terms

1. Duration: 12 months.
2. Payment: monthly, net 30.
""",
}

samples = [
    ("ar_research", ar_research),
    ("en_childrens_book", en_childrens_book),
    ("en_contract", en_contract),
]

for name, plan in samples:
    for i in range(2):
        out = f"test_out_{name}_{i}.pdf"
        render_pdf(dict(plan), out)
        print("rendered", out)
