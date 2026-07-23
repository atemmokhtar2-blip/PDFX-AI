"""
Renders a PDFX AI document plan (see analyzer.py) into a polished PDF using
Jinja2 + Markdown + WeasyPrint, driven by the Design Intelligence Engine
(design_engine.py) and the smart content-box extractor (content_boxes.py).

There is no fixed "template" here in the old sense: `build_design_spec`
picks a fresh palette + cover layout + heading style + motif combination
for every single document (tone-aware, never asking the user), and the one
HTML/CSS skeleton renders whatever combination it's given.
"""

import os
import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from content_boxes import extract_boxes, reinsert_boxes
from design_engine import build_design_spec

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

FONT_STACK_RTL = "'Noto Naskh Arabic', 'Noto Sans Arabic', 'Noto Sans', sans-serif"
FONT_STACK_LTR = "'Noto Sans', 'Noto Naskh Arabic', sans-serif"

DOC_TYPE_LABELS_AR = {
    "report": "تقرير", "research": "بحث", "article": "مقال", "book": "كتاب",
    "summary": "ملخص", "memo": "مذكرة", "cv": "سيرة ذاتية", "invoice": "فاتورة",
    "letter": "خطاب رسمي", "contract": "عقد", "business_plan": "خطة عمل",
    "proposal": "عرض مشروع", "exam": "امتحان", "quiz": "اختبار", "study_guide": "دليل دراسي", "general": "مستند",
}
DOC_TYPE_LABELS_EN = {
    "report": "Report", "research": "Research Paper", "article": "Article",
    "book": "Book", "summary": "Summary", "memo": "Memo", "cv": "Curriculum Vitae",
    "invoice": "Invoice", "letter": "Formal Letter", "contract": "Contract",
    "business_plan": "Business Plan",     "proposal": "Project Proposal", "exam": "Exam", "quiz": "Quiz", "study_guide": "Study Guide", "general": "Document",
}

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _markdown_to_html_and_headings(content_markdown: str, rtl: bool):
    # Pull out smart content boxes (:::definition, :::warning, :::steps, ...)
    # before the general Markdown pass so they render as their own styled
    # blocks instead of being treated as plain paragraphs/code fences.
    patched_markdown, box_renders = extract_boxes(content_markdown, rtl)

    md = markdown.Markdown(extensions=["tables", "toc", "fenced_code", "nl2br", "sane_lists"])
    html = md.convert(patched_markdown or "")
    html = reinsert_boxes(html, box_renders)

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

    # The Design Intelligence Engine makes every visual decision for this
    # specific document: palette, cover layout, heading style, TOC style,
    # motif, density. It is re-rolled on every call, so no two documents
    # render identically even for the same doc_type/tone.
    design = build_design_spec(plan)

    body_html, headings = _markdown_to_html_and_headings(plan.get("content_markdown", ""), rtl)

    # Only show TOC if it was requested AND there are actually enough headings
    plan["needs_toc"] = bool(plan.get("needs_toc")) and len(headings) >= 3

    doc_type_label = (DOC_TYPE_LABELS_AR if rtl else DOC_TYPE_LABELS_EN).get(
        plan.get("doc_type", "general"), "مستند" if rtl else "Document"
    )

    template = _env.get_template("document.html.j2")
    html_str = template.render(
        plan=plan,
        design=design,
        body_html=body_html,
        headings=headings,
        doc_type_label=doc_type_label,
        font_stack=FONT_STACK_RTL if rtl else FONT_STACK_LTR,
        page_side="right" if rtl else "left",
        page_other_side="left" if rtl else "right",
        page_label_prefix="صفحة " if rtl else "Page ",
        page_label_mid=" من " if rtl else " of ",
        tone_class=f"tone-{design.tone}" if design.tone else "",
    )

    HTML(string=html_str, base_url=BASE_DIR).write_pdf(output_path)
    return output_path
