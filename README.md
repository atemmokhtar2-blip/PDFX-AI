# PDFX AI

**PDFX AI** is not just a text-to-PDF converter — it's an AI-powered document
designer. Send it any raw text on Telegram and it analyzes the content,
figures out what kind of document it is, corrects and organizes the writing,
and produces a polished, print-ready PDF automatically.

## How it works

1. User sends plain text to the Telegram bot. No type/template/style choice
   is ever asked — the user only ever sends content.
2. The text is sent to an AI model (via the Kilo Gateway, OpenAI-compatible
   API) which returns a structured "document plan": detected type, **tone**
   (the document's personality — formal, medical, playful, technical, ...),
   language, direction, title, and a cleaned-up, well-organized Markdown
   body. The model also marks up specific content (definitions, warnings,
   highlights, quotes, notes, step sequences, statistics, comparisons)
   inline using a small `:::kind ... :::` fence syntax.
3. The **Design Intelligence Engine** (`design_engine.py`) makes every
   visual decision for that specific document — color palette, cover
   layout, heading style, table-of-contents style, decorative motif, page
   density — based on the tone/content profile, with built-in randomization
   so two documents never render identically, even for the same doc type
   and even for the same input text rendered twice.
4. `content_boxes.py` turns the `:::kind` fences into styled boxes: a
   numbered timeline for `:::steps`, a stat-card grid for `:::stats`, a
   comparison table for `:::compare`, and titled callout boxes for
   `:::definition` / `:::warning` / `:::highlight` / `:::quote` / `:::note`.
5. The plan + design spec are rendered into a professional PDF with
   [WeasyPrint](https://weasyprint.org/): cover page, header/footer, page
   numbers, auto-generated table of contents (for longer docs), tables,
   lists, smart content boxes, and full Arabic (RTL) / English (LTR) /
   mixed support.
6. The finished PDF is sent back to the user in the chat.

## Supported document types

Report, research paper, article, book, summary, memo, CV, invoice, formal
letter, contract, business plan, project proposal, and general documents.
The type — and its tone/personality — is detected automatically. The user
never chooses a type, a template, or a design.

## Design — no templates, no fixed theme

There is no template picker and no single fixed color theme. Every
document gets its own palette (chosen from tone-appropriate color families
with random hue/lightness jitter), its own cover layout variant, heading
style, TOC style, and page density, decided by the Design Intelligence
Engine at render time. A calm/formal document (contract, medical research)
stays restrained; a playful document (children's book, personal note) can
be more expressive — but the *specific* combination is re-rolled every
time, so no two documents — even identical ones — look pixel-identical.

## Stack

- `python-telegram-bot` — Telegram bot framework
- Kilo Gateway (OpenAI-compatible chat completions) — content analysis &
  writing/formatting via a free-tier model by default (`kilo-auto/free`)
- `Jinja2` + `markdown` — turns the AI's Markdown into styled HTML
- `WeasyPrint` — HTML/CSS to PDF rendering (no headless browser needed)
- Noto Naskh Arabic / Noto Sans Arabic / Noto Sans fonts, embedded in the PDF

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # or use uv, see below
```

System dependencies (Debian/Ubuntu):

```bash
apt-get install -y fonts-noto-core fonts-noto-extra
```

Copy `run_bot.sh.example` to `run_bot.sh`, fill in your bot token, then:

```bash
chmod +x run_bot.sh
./run_bot.sh
```

Environment variables:

- `PDFX_BOT_TOKEN` — Telegram bot token (required)
- `KILOCODE_API_KEY` / `KILO_API_KEY` — Kilo Gateway API key (required)
- `PDFX_MODEL` — model id to use for analysis (default: `kilo-auto/free`)

## Files

- `bot.py` — Telegram bot entry point (handlers, welcome message, flow)
- `analyzer.py` — sends text to the AI, parses/validates the returned plan
  (including `tone` and inline `:::kind` boxes), with automatic fallback
  across free models and contamination detection
- `design_engine.py` — the Design Intelligence Engine: picks a fresh,
  tone-aware palette/cover/heading/TOC/motif/density combination for every
  document, with controlled randomization so nothing repeats
- `content_boxes.py` — extracts `:::definition` / `:::warning` /
  `:::highlight` / `:::quote` / `:::note` / `:::steps` / `:::stats` /
  `:::compare` fences from the Markdown and renders each as its own styled
  HTML block (timeline, stat cards, callout box, etc.)
- `renderer.py` — turns a document plan + design spec into a PDF via
  Jinja2 + WeasyPrint
- `templates/document.html.j2` — page structure (cover, TOC, content) —
  one skeleton, driven entirely by the design spec's CSS classes
- `templates/style.css.j2` — the print stylesheet: CSS variables for the
  palette, plus variant rules for every cover/heading/TOC/motif option and
  the smart content boxes, RTL/LTR aware, headers/footers, page numbers
