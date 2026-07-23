# PDFX AI

**PDFX AI** is not just a text-to-PDF converter — it's an AI-powered document
designer. Send it any raw text on Telegram and it analyzes the content,
figures out what kind of document it is, corrects and organizes the writing,
and produces a polished, print-ready PDF automatically.

## How it works

1. User sends plain text to the Telegram bot.
2. The text is sent to an AI model (via the Kilo Gateway, OpenAI-compatible
   API) which returns a structured "document plan": detected type, language,
   direction, title, and a cleaned-up, well-organized Markdown body.
3. The plan is rendered into a professional PDF with
   [WeasyPrint](https://weasyprint.org/): cover page, header/footer, page
   numbers, auto-generated table of contents (for longer docs), tables,
   lists, and full Arabic (RTL) / English (LTR) / mixed support.
4. The finished PDF is sent back to the user in the chat.

## Supported document types

Report, research paper, article, book, summary, memo, CV, invoice, formal
letter, contract, business plan, project proposal, and general documents.
The type is detected automatically — the user never has to choose.

## Design

Clean, modern, print-ready layout in a white / blue / gray palette, with a
generated cover page and consistent header/footer/page numbering on every
page.

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
- `analyzer.py` — sends text to the AI, parses/validates the returned plan,
  with automatic fallback across free models and contamination detection
- `renderer.py` — turns a document plan into a PDF via Jinja2 + WeasyPrint
- `templates/document.html.j2` — page structure (cover, TOC, content)
- `templates/style.css.j2` — the print stylesheet (blue/white/gray theme,
  RTL/LTR aware, headers/footers, page numbers)
