"""
AI document analyzer for PDFX AI.
Sends raw user text to the Kilo Gateway (OpenAI-compatible) chat completions
endpoint and gets back a structured document plan (JSON) that the renderer
turns into a polished PDF.
"""

import json
import os
import re
import httpx

from design_engine import TONES

KILO_BASE_URL = "https://api.kilo.ai/api/gateway/"
KILO_MODEL = os.environ.get("PDFX_MODEL", "kilo-auto/free")
KILO_API_KEY = os.environ.get("KILOCODE_API_KEY") or os.environ.get("KILO_API_KEY")

DOC_TYPES = [
    "report", "research", "article", "book", "summary", "memo", "cv",
    "invoice", "letter", "contract", "business_plan", "proposal", "general",
]

SYSTEM_PROMPT = """You are PDFX AI's content analyst. You take raw, possibly messy user text (Arabic, English, or mixed) and turn it into a structured, corrected, professionally organized document plan. You do NOT pick a visual template or ask the user anything — a separate Design Intelligence Engine handles 100% of the visual design from what you return. Your only job is understanding and organizing the content.

Output ONLY a single valid JSON object. No markdown fences. No commentary. No explanation before or after. The JSON must be syntactically valid (escape all quotes and newlines with \\n).

Schema:
{
  "doc_type": one of ["report","research","article","book","summary","memo","cv","invoice","letter","contract","business_plan","proposal","general"],
  "tone": one of ["formal","academic","technical","business","medical","legal","educational","creative","friendly","personal","playful"] — the document's PERSONALITY, more specific than doc_type. E.g. a "research" doc_type can be tone="medical", "academic", or "technical" depending on the actual subject; a children's story is tone="playful" even though doc_type="book".
  "language": "ar" | "en" | "mixed",
  "direction": "rtl" | "ltr",
  "title": "short descriptive title for the document",
  "subtitle": "short subtitle or null",
  "author": "author name if mentioned in the text, else null",
  "date": "date if mentioned or relevant, else null",
  "needs_cover": true|false (true for longer/formal docs like reports, research, books, business plans, contracts, CVs; false for short memos/letters),
  "needs_toc": true|false (true only if the document has 3+ major sections and is reasonably long),
  "content_markdown": "the full corrected, well-organized document body, written in Markdown, using the smart-box syntax below wherever it fits"
}

Rules for content_markdown:
- Fix spelling and grammar mistakes.
- Improve wording to sound professional, keep the original meaning and facts.
- Organize into logical sections with clear headings using Markdown: use ## for section headings, ### for subsections. Do NOT use a single # (that's the title, handled separately).
- Use "- " for bullet lists, "1. " for numbered lists.
- Use Markdown pipe tables ( | col | col | ) for straightforward tabular data (e.g. invoice line items, schedules) that doesn't fit a smart box below.
- Keep the SAME language as the input (Arabic input -> Arabic output, English input -> English output, mixed -> keep mixed naturally).
- For a CV: organize as sections like Summary, Experience, Education, Skills, Languages.
- For an invoice: include a Markdown table with items, quantities, prices, totals.
- For a letter/memo: keep it concise, don't over-section short content.
- Never invent facts, numbers, or names not present or implied in the input. Only correct/organize/improve wording.

Smart content boxes — use this fenced syntax INLINE in content_markdown whenever the underlying content actually calls for it (don't force it, only use where it genuinely improves clarity):

  :::definition Term or title
  The definition text (markdown allowed).
  :::

  :::warning
  Important caution or risk the reader must not miss.
  :::

  :::highlight
  A key takeaway or standout fact worth visually emphasizing.
  :::

  :::quote
  A direct quotation from the source text.
  :::

  :::note
  A secondary remark or aside.
  :::

  :::steps
  - First step description
  - Second step description
  - Third step description
  :::
  (use :::steps whenever the content describes a sequence/process/instructions — it renders as a numbered timeline, not a plain list)

  :::stats
  - 42%: of users reported X
  - 3.2M: total downloads
  :::
  (use :::stats whenever the content has standout numeric figures — each line is "value: label" and renders as a stat card grid)

  :::compare
  | Feature | Option A | Option B |
  | --- | --- | --- |
  | ... | ... | ... |
  :::
  (use :::compare specifically for side-by-side comparisons, distinct from a generic data table)

  :::question QuestionNumber
  Question text and options...
  :::
  (use :::question for every individual question or exam item)

  :::image Caption
  image_path_or_id
  :::
  (use :::image for all visual elements to ensure professional framing)

Each box's fence markers (`:::kind ...` and the closing `:::`) must be on their own line with a blank line before and after. Never nest boxes inside each other.

For EDUCATIONAL/EXAM content:
- Prioritize whitespace and readability.
- Wrap every question in a `:::question` block.
- If a question has an image, keep it INSIDE the `:::question` block.
- Use `:::image` for any visual elements to ensure professional framing.
- Ensure clear separation between questions.
"""


class AnalyzerError(Exception):
    pass


_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"  # CJK Unified, Hiragana/Katakana, Hangul
)


def _has_unexpected_script_contamination(plan: dict) -> bool:
    """Cheap free-tier models occasionally leak stray CJK/Hangul tokens into
    otherwise Arabic/English output. Detect that so we can retry with a
    different model instead of shipping a broken document."""
    text = (plan.get("content_markdown") or "") + (plan.get("title") or "")
    return bool(_CJK_RE.search(text))


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if the model added them anyway
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: find the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)
    raise AnalyzerError("Model did not return valid JSON")


# Fallback free models to try if the primary one returns an empty/invalid response
# (shared free-tier models can be flaky under load).
FALLBACK_MODELS = ["kilo-auto/free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "poolside/laguna-s-2.1:free"]


def _call_model(model: str, user_text: str, timeout: float, system_hint: str = "") -> str:
    full_system_prompt = SYSTEM_PROMPT
    if system_hint:
        full_system_prompt += f"\n\nIMPORTANT CONTEXT: {system_hint}"
        
    # Use a faster model if possible, and optimize max_tokens
    payload = {
        "model": model,
        "reasoning": {"exclude": True},
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 5000 if "REDESIGN" in system_hint else 3000,
        "temperature": 0.3, # Lower temperature for faster/more consistent output
    }
    headers = {
        "Authorization": f"Bearer {KILO_API_KEY}",
        "Content-Type": "application/json",
        "X-KILOCODE-FEATURE": "openclaw",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(KILO_BASE_URL + "chat/completions", json=payload, headers=headers)
    if resp.status_code != 200:
        raise AnalyzerError(f"AI request failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    if "error" in data:
        raise AnalyzerError(f"AI error: {data['error']}")
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise AnalyzerError("Unexpected AI response shape")
    if not content:
        raise AnalyzerError("Empty AI response")
    return content


def analyze_text(user_text: str, timeout: float = 120.0, system_hint: str = "") -> dict:
    if not KILO_API_KEY:
        raise AnalyzerError("Missing KILOCODE_API_KEY")

    models_to_try = [KILO_MODEL] + [m for m in FALLBACK_MODELS if m != KILO_MODEL]

    last_error = None
    plan = None
    for model in models_to_try:
        try:
            content = _call_model(model, user_text, timeout, system_hint)
        except AnalyzerError as e:
            last_error = e
            continue
        try:
            candidate = _extract_json(content)
        except Exception as e:
            last_error = AnalyzerError(f"Invalid JSON from {model}: {e}")
            continue
        if _has_unexpected_script_contamination(candidate):
            last_error = AnalyzerError(f"Script contamination from {model}")
            continue
        plan = candidate
        break

    if plan is None:
        raise last_error or AnalyzerError("AI request failed")

    # Normalize / validate
    plan.setdefault("doc_type", "general")
    if plan["doc_type"] not in DOC_TYPES:
        plan["doc_type"] = "general"
    tone = (plan.get("tone") or "").strip().lower()
    plan["tone"] = tone if tone in TONES else None
    plan.setdefault("language", "ar")
    plan.setdefault("direction", "rtl" if plan["language"] in ("ar", "mixed") else "ltr")
    plan.setdefault("title", "مستند" if plan["language"] == "ar" else "Document")
    plan.setdefault("subtitle", None)
    plan.setdefault("author", None)
    plan.setdefault("date", None)
    plan.setdefault("needs_cover", plan["doc_type"] in (
        "report", "research", "book", "business_plan", "contract", "cv", "proposal"
    ))
    plan.setdefault("needs_toc", False)
    plan.setdefault("content_markdown", "")

    return plan
