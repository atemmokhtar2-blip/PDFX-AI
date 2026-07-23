"""
Content-aware "smart boxes" for PDFX AI's Design Intelligence Engine.

The AI analyzer is instructed (see analyzer.py's SYSTEM_PROMPT) to mark up
specific content types inline in the Markdown it returns, using a small
fenced-block convention:

    :::definition Title (optional)
    body markdown...
    :::

Supported box kinds: definition, warning, highlight, quote, note, steps,
compare, stats.

This module extracts those fenced blocks *before* the main Markdown pass
(so they can't be mangled by the outer parser), renders each one's own
inner Markdown, and produces a styled HTML fragment. The main document
Markdown is left with opaque placeholder tokens that get substituted back
in after the main conversion.

`steps` renders as a vertical timeline; `stats` renders as a grid of stat
cards (each line `value: label`); everything else renders as a titled
callout box. This is what lets the renderer honor sections 7 and 8 of the
design spec (statistics -> charts/cards, steps -> timeline, comparisons ->
tables, definitions/warnings/highlights/quotes/notes -> boxes) without any
user choice involved.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple

import markdown as _markdown_module

BOX_KINDS = {
    "definition", "warning", "highlight", "quote", "note", "steps",
    "compare", "stats", "image",
}

_FENCE_RE = re.compile(
    r"^:::(?P<kind>[a-zA-Z]+)[ \t]*(?P<title>[^\n]*)\n"
    r"(?P<body>.*?)\n^:::[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

_STAT_LINE_RE = re.compile(r"^\s*[-*]?\s*(?P<value>[^\n:]{1,24}):\s*(?P<label>.+)$")


def _inline_md(text: str) -> str:
    """Render a small chunk of markdown to HTML for use inside a box."""
    return _markdown_module.markdown(
        text.strip(), extensions=["tables", "fenced_code", "nl2br", "sane_lists"]
    ).strip()


@dataclass
class BoxRender:
    token: str
    html: str


def _render_steps(body: str) -> str:
    items = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s*", "", line)
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        if ":" in line:
            head, _, rest = line.partition(":")
            items.append((head.strip(), rest.strip()))
        else:
            items.append((None, line))

    parts = ['<div class="box box-steps">']
    for i, (head, rest) in enumerate(items, 1):
        parts.append('<div class="step-item">')
        parts.append(f'<div class="step-num">{i}</div>')
        parts.append('<div class="step-body">')
        if head:
            parts.append(f'<div class="step-head">{head}</div>')
        parts.append(f"<div class=\"step-text\">{_inline_md(rest)}</div>")
        parts.append("</div></div>")
    parts.append("</div>")
    return "".join(parts)


def _render_stats(body: str) -> str:
    cards = []
    for line in body.strip().splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line:
            continue
        m = _STAT_LINE_RE.match(line)
        if m:
            value, label = m.group("value").strip(), m.group("label").strip()
        else:
            value, label = line, ""
        cards.append((value, label))

    parts = ['<div class="box box-stats">']
    for value, label in cards:
        parts.append(
            f'<div class="stat-card"><div class="stat-value">{value}</div>'
            f'<div class="stat-label">{label}</div></div>'
        )
    parts.append("</div>")
    return "".join(parts)


_KIND_LABELS_AR = {
    "definition": "تعريف", "warning": "تحذير", "highlight": "مهم",
    "quote": "اقتباس", "note": "ملاحظة",
}
_KIND_LABELS_EN = {
    "definition": "Definition", "warning": "Warning", "highlight": "Highlight",
    "quote": "Quote", "note": "Note",
}
_KIND_ICONS = {
    "definition": "\U0001F4D8", "warning": "\u26A0\uFE0F", "highlight": "\u2728",
    "quote": "\u275D", "note": "\U0001F4CC",
}


def _render_callout(kind: str, title: str, body: str, rtl: bool) -> str:
    label = (_KIND_LABELS_AR if rtl else _KIND_LABELS_EN).get(kind, kind.title())
    icon = _KIND_ICONS.get(kind, "")
    heading = title.strip() or label
    return (
        f'<div class="box box-{kind}">'
        f'<div class="box-head"><span class="box-icon">{icon}</span>'
        f'<span class="box-title">{heading}</span></div>'
        f'<div class="box-body">{_inline_md(body)}</div>'
        f"</div>"
    )


def _render_compare(body: str) -> str:
    # The AI is expected to put a Markdown table here; render it through the
    # normal markdown pipeline and wrap it for comparison-specific styling.
    html = _inline_md(body)
    return f'<div class="box box-compare">{html}</div>'


def _render_image(title: str, body: str) -> str:
    # body is expected to be the image path or index
    path = body.strip()
    caption = title.strip()
    return (
        f'<div class="box box-image">'
        f'<img src="{path}" style="max-width: 100%; height: auto; border-radius: 8px;">'
        f'{f"<div class=\'image-caption\'>{caption}</div>" if caption else ""}'
        f'</div>'
    )


def extract_boxes(content_markdown: str, rtl: bool) -> Tuple[str, Dict[str, str]]:
    """Replace every `:::kind ... :::` fence with a unique placeholder token
    and return (patched_markdown, {token: rendered_html})."""
    renders: Dict[str, str] = {}

    def _sub(match: "re.Match") -> str:
        kind = match.group("kind").lower()
        title = (match.group("title") or "").strip()
        body = match.group("body") or ""
        if kind not in BOX_KINDS:
            return match.group(0)

        if kind == "steps":
            html = _render_steps(body)
        elif kind == "stats":
            html = _render_stats(body)
        elif kind == "compare":
            html = _render_compare(body)
        elif kind == "image":
            html = _render_image(title, body)
        else:
            html = _render_callout(kind, title, body, rtl)

        token = f"PDFXBOX{uuid.uuid4().hex}PDFXBOX"
        renders[token] = html
        # Blank lines around the token so the outer Markdown parser treats
        # it as its own block and doesn't wrap it in a <p>.
        return f"\n\n{token}\n\n"

    patched = _FENCE_RE.sub(_sub, content_markdown or "")
    return patched, renders


def reinsert_boxes(html: str, renders: Dict[str, str]) -> str:
    for token, box_html in renders.items():
        # Markdown wraps bare-line tokens in <p>...</p>; strip that wrapper
        # if present so the box div isn't nested inside a paragraph.
        html = html.replace(f"<p>{token}</p>", box_html)
        html = html.replace(token, box_html)
    return html
