"""
Renders a PDFX AI document plan (see analyzer.py) into a polished PDF using
Jinja2 + Markdown + WeasyPrint.
"""

import os
import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

FONT_STACK_RTL = "'Noto Naskh Arabic', 'Noto Sans Arabic', 'Noto Sans', sans-serif"
FONT_STACK_LTR = "'Noto Sans', 'Noto Naskh Arabic', sans-serif"

DOC_TYPE_LABELS_AR = {
    "report": "تقرير", "research": "بحث", "article": "مقال", "book": "كتاب",
    "summary": "ملخص", "memo": "مذكرة", "cv": "سيرة ذاتية", "invoice": "فاتورة",
    "letter": "خطاب رسمي", "contract": "عقد", "business_plan": "خطة عمل",
    "proposal": "عرض مشروع", "general": "مستند",
}
DOC_TYPE_LABELS_EN = {
    "report": "Report", "research": "Research Paper", "article": "Article",
    "book": "Book", "summary": "Summary", "memo": "Memo", "cv": "Curriculum Vitae",
    "invoice": "Invoice", "letter": "Formal Letter", "contract": "Contract",
    "business_plan": "Business Plan", "proposal": "Project Proposal", "general": "Document",
}

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _markdown_to_html_and_headings(content_markdown: str):
    md = markdown.Markdown(extensions=["tables", "toc", "fenced_code", "nl2br", "sane_lists"])
    html = md.convert(content_markdown or "")
    headings = []
    for tok in getattr(md, "toc_tokens", []):
        headings.append({
            "id": tok["id"],
            "text": tok["name"],
            "level": 1 if tok["level"] <= 2 else 2,
        })
    return html, headings


def render_pdf(plan: dict, output_path: str) -> str:
    rtl = plan.get("direction") == "rtl"
    body_html, headings = _markdown_to_html_and_headings(plan.get("content_markdown", ""))

    # Only show TOC if it was requested AND there are actually enough headings
    plan["needs_toc"] = bool(plan.get("needs_toc")) and len(headings) >= 3

    doc_type_label = (DOC_TYPE_LABELS_AR if rtl else DOC_TYPE_LABELS_EN).get(
        plan.get("doc_type", "general"), "مستند" if rtl else "Document"
    )

    template = _env.get_template("document.html.j2")
    html_str = template.render(
        plan=plan,
        body_html=body_html,
        headings=headings,
        doc_type_label=doc_type_label,
        font_stack=FONT_STACK_RTL if rtl else FONT_STACK_LTR,
        page_side="right" if rtl else "left",
        page_other_side="left" if rtl else "right",
        page_label_prefix="صفحة " if rtl else "Page ",
        page_label_mid=" من " if rtl else " of ",
    )

    HTML(string=html_str, base_url=BASE_DIR).write_pdf(output_path)
    return output_path
