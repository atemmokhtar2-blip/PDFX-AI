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

KILO_BASE_URL = "https://api.kilo.ai/api/gateway/"
KILO_MODEL = os.environ.get("PDFX_MODEL", "kilo-auto/free")
KILO_API_KEY = os.environ.get("KILOCODE_API_KEY") or os.environ.get("KILO_API_KEY")

DOC_TYPES = [
    "report", "research", "article", "book", "summary", "memo", "cv",
    "invoice", "letter", "contract", "business_plan", "proposal", "general",
]

SYSTEM_PROMPT = """You are PDFX AI, a professional AI document designer. You take raw, possibly messy user text (Arabic, English, or mixed) and turn it into a structured, corrected, professionally organized document plan.

Output ONLY a single valid JSON object. No markdown fences. No commentary. No explanation before or after. The JSON must be syntactically valid (escape all quotes and newlines with \\n).

Schema:
{
  "doc_type": one of ["report","research","article","book","summary","memo","cv","invoice","letter","contract","business_plan","proposal","general"],
  "language": "ar" | "en" | "mixed",
  "direction": "rtl" | "ltr",
  "title": "short descriptive title for the document",
  "subtitle": "short subtitle or null",
  "author": "author name if mentioned in the text, else null",
  "date": "date if mentioned or relevant, else null",
  "needs_cover": true|false (true for longer/formal docs like reports, research, books, business plans, contracts, CVs; false for short memos/letters),
  "needs_toc": true|false (true only if the document has 3+ major sections and is reasonably long),
  "content_markdown": "the full corrected, well-organized document body, written in Markdown"
}

Rules for content_markdown:
- Fix spelling and grammar mistakes.
- Improve wording to sound professional, keep the original meaning and facts.
- Organize into logical sections with clear headings using Markdown: use ## for section headings, ### for subsections. Do NOT use a single # (that's the title, handled separately).
- Use "- " for bullet lists, "1. " for numbered lists.
- Use Markdown pipe tables ( | col | col | ) when the content has tabular/structured data (e.g. invoices, comparisons, schedules).
- Keep the SAME language as the input (Arabic input -> Arabic output, English input -> English output, mixed -> keep mixed naturally).
- For a CV: organize as sections like Summary, Experience, Education, Skills, Languages.
- For an invoice: include a Markdown table with items, quantities, prices, totals.
- For a letter/memo: keep it concise, don't over-section short content.
- Never invent facts, numbers, or names not present or implied in the input. Only correct/organize/improve wording.
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


def _call_model(model: str, user_text: str, timeout: float) -> str:
    payload = {
        "model": model,
        "reasoning": {"exclude": True},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 4000,
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


def analyze_text(user_text: str, timeout: float = 90.0) -> dict:
    if not KILO_API_KEY:
        raise AnalyzerError("Missing KILOCODE_API_KEY")

    models_to_try = [KILO_MODEL] + [m for m in FALLBACK_MODELS if m != KILO_MODEL]

    last_error = None
    plan = None
    for model in models_to_try:
        try:
            content = _call_model(model, user_text, timeout)
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
