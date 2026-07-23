
import os
from renderer import render_pdf

plan = {
    "doc_type": "exam",
    "tone": "educational",
    "language": "ar",
    "direction": "rtl",
    "title": "اختبار مادة الفيزياء - الصف الثالث الثانوي",
    "subtitle": "الفصل الدراسي الأول - نموذج أ",
    "author": "وزارة التربية والتعليم",
    "date": "يوليو 2026",
    "needs_cover": True,
    "needs_toc": False,
    "content_markdown": """
## الأسئلة المقالية

:::question 1
اشرح قانون نيوتن الثالث للحركة مع ذكر مثال من الواقع العملي.
:::

:::question 2
احسب القوة اللازمة لتحريك كتلة قدرها 5 كجم بعجلة قدرها 2 م/ث².
:::

## أسئلة الاختيار من متعدد

:::question 3
ما هي وحدة قياس القوة في النظام الدولي للوحدات؟
- أ) جول
- ب) نيوتن
- ج) وات
- د) باسكال
:::

:::question 4
انظر إلى الشكل التالي ثم أجب:
:::image رسم توضيحي للقوى المؤثرة على جسم
https://placehold.co/600x400?text=Physics+Diagram
:::
ما هي القوة المحصلة المؤثرة على الجسم في اتجاه اليمين؟
:::
"""
}

if __name__ == "__main__":
    output_path = "test_educational.pdf"
    render_pdf(plan, output_path)
    print(f"Rendered {output_path}")
