"""
Design Intelligence Engine for PDFX AI.

This module is the "design brain" of the document generator. It never
produces the same visual result twice, and it never asks the user to choose
anything. Instead it reads a *content profile* (derived from the AI's
document plan) and makes every visual decision itself:

  - color palette (picked from curated, tone-appropriate families, with a
    small random hue/lightness nudge so even the *same* family never looks
    exactly the same twice)
  - cover layout variant
  - heading / section style
  - table-of-contents style
  - decorative motif + density (how airy/compact the page feels)

Nothing here is a "template" in the old sense: there is one HTML/CSS
skeleton, and this engine drives it with a fresh combination of parameters
on every call so 100 documents of the same doc_type never look alike, while
still respecting the *personality* of the content (a formal contract should
still read as calm and serious; a children's story can be playful).
"""

from __future__ import annotations

import colorsys
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Tone vocabulary
# ---------------------------------------------------------------------------
# The analyzer is asked to classify the document's *personality* (not just
# its doc_type). This is deliberately more granular than doc_type: two
# "research" documents (medical vs school) get different tones and
# therefore different design decisions.

TONES = [
    "formal", "academic", "technical", "business", "medical", "legal",
    "educational", "creative", "friendly", "personal", "playful",
]

_DOC_TYPE_TONE_HINTS = {
    "report": "business", "research": "academic", "article": "editorial",
    "book": "creative", "summary": "editorial", "memo": "business",
    "cv": "business", "invoice": "formal", "letter": "formal",
    "contract": "legal", "business_plan": "business", "proposal": "business",
    "general": "friendly",
}


def infer_tone(plan: Dict[str, Any]) -> str:
    """Best-effort tone if the AI plan didn't already include one."""
    tone = (plan.get("tone") or "").strip().lower()
    if tone in TONES:
        return tone
    return _DOC_TYPE_TONE_HINTS.get(plan.get("doc_type", "general"), "friendly")


# ---------------------------------------------------------------------------
# Palette families
# ---------------------------------------------------------------------------
# Each family is a curated, print-safe combination. The engine still nudges
# hue/lightness slightly at random so no two documents share pixel-identical
# colors, but it never strays into an unreadable/clashing combination.

@dataclass
class Palette:
    name: str
    primary: str
    primary_light: str
    accent: str
    accent_wash: str
    surface_alt: str
    ink: str = "#1a1a2e"
    muted: str = "#5b6472"
    line: str = "#e4e8ee"


_PALETTE_FAMILIES: List[Dict[str, Any]] = [
    {"name": "deep-ocean", "tones": ["formal", "business", "legal", "academic"],
     "primary": (210, 65, 24), "accent": (204, 68, 55), "surface_alt": (210, 35, 96)},
    {"name": "forest", "tones": ["academic", "educational", "medical", "formal"],
     "primary": (152, 45, 22), "accent": (152, 45, 42), "surface_alt": (140, 30, 96)},
    {"name": "charcoal-amber", "tones": ["technical", "business", "formal"],
     "primary": (222, 15, 16), "accent": (38, 78, 58), "surface_alt": (35, 22, 95)},
    {"name": "plum", "tones": ["creative", "personal", "editorial", "playful"],
     "primary": (317, 45, 22), "accent": (344, 70, 45), "surface_alt": (320, 35, 96)},
    {"name": "slate-teal", "tones": ["technical", "business", "medical"],
     "primary": (177, 60, 15), "accent": (172, 60, 47), "surface_alt": (175, 35, 96)},
    {"name": "terracotta", "tones": ["creative", "personal", "educational", "friendly", "playful"],
     "primary": (16, 70, 28), "accent": (38, 90, 55), "surface_alt": (28, 45, 96)},
    {"name": "indigo", "tones": ["formal", "technical", "academic", "business"],
     "primary": (248, 45, 20), "accent": (243, 75, 60), "surface_alt": (240, 40, 96)},
    {"name": "rose-gold", "tones": ["creative", "personal", "friendly", "playful"],
     "primary": (330, 60, 28), "accent": (330, 75, 65), "surface_alt": (330, 40, 96)},
    {"name": "sunny", "tones": ["friendly", "educational", "personal", "playful"],
     "primary": (32, 90, 27), "accent": (48, 90, 55), "surface_alt": (45, 55, 95)},
    {"name": "midnight-cyan", "tones": ["technical", "business", "editorial"],
     "primary": (222, 45, 12), "accent": (200, 90, 55), "surface_alt": (210, 40, 96)},
]


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h = h % 360 / 360.0
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _nudge(hsl: tuple, rng: random.Random, hue_jitter=6, sat_jitter=0.05, light_jitter=0.03):
    h, s, l = hsl
    h = h + rng.uniform(-hue_jitter, hue_jitter)
    s = s / 100.0 + rng.uniform(-sat_jitter, sat_jitter)
    l = l / 100.0 + rng.uniform(-light_jitter, light_jitter)
    return h, s, l


def _build_palette(family: Dict[str, Any], rng: random.Random) -> Palette:
    ph, ps, pl = _nudge(family["primary"], rng)
    ah, as_, al = _nudge(family["accent"], rng, hue_jitter=8, sat_jitter=0.06, light_jitter=0.04)
    sh, ss, sl = _nudge(family["surface_alt"], rng, hue_jitter=4, sat_jitter=0.04, light_jitter=0.02)

    primary = _hsl_to_hex(ph, ps, pl)
    primary_light = _hsl_to_hex(ph, ps * 0.92, min(0.62, pl + 0.16))
    accent = _hsl_to_hex(ah, as_, al)
    accent_wash = _hsl_to_hex(ah, as_ * 0.7, min(0.94, al + 0.35))
    surface_alt = _hsl_to_hex(sh, ss, min(0.97, max(0.9, sl)))

    return Palette(
        name=family["name"],
        primary=primary,
        primary_light=primary_light,
        accent=accent,
        accent_wash=accent_wash,
        surface_alt=surface_alt,
    )


def _pick_palette(tone: str, rng: random.Random) -> Palette:
    candidates = [f for f in _PALETTE_FAMILIES if tone in f["tones"]] or _PALETTE_FAMILIES
    family = rng.choice(candidates)
    return _build_palette(family, rng)


# ---------------------------------------------------------------------------
# Layout / style vocabulary
# ---------------------------------------------------------------------------

COVER_VARIANTS = ["band-top", "diagonal-split", "sidebar-block", "centered-frame", "corner-shape", "minimal-rule"]
HEADING_STYLES = ["underline", "left-bar", "accent-dot", "boxed-number"]
TOC_STYLES = ["dotted-leader", "numbered-chips"]
MOTIFS = ["dots", "lines", "none", "grid"]

# Some combinations read poorly for very formal/legal content (too playful);
# keep those documents restrained while still varying within a tasteful set.
_RESTRAINED_TONES = {"formal", "legal", "medical", "academic"}
_RESTRAINED_COVERS = ["band-top", "minimal-rule", "centered-frame", "sidebar-block"]
_RESTRAINED_MOTIFS = ["none", "lines"]
_PLAYFUL_TONES = {"playful", "friendly", "creative", "personal"}


@dataclass
class DesignSpec:
    palette: Palette
    cover_variant: str
    heading_style: str
    toc_style: str
    motif: str
    density: str  # "airy" | "compact"
    rounded: bool
    tone: str
    seed_tag: str


def build_design_spec(plan: Dict[str, Any], rng: Optional[random.Random] = None) -> DesignSpec:
    """Make every visual decision for this document. Called once per PDF.

    Uses OS entropy by default (no fixed seed) so consecutive documents,
    even with identical content, never render identically.
    """
    rng = rng or random.Random()  # seeded from OS entropy -> non-repeating
    tone = infer_tone(plan)

    palette = _pick_palette(tone, rng)

    if tone in _RESTRAINED_TONES:
        cover_variant = rng.choice(_RESTRAINED_COVERS)
        motif = rng.choice(_RESTRAINED_MOTIFS)
        heading_style = rng.choice(["underline", "left-bar", "boxed-number"])
    else:
        cover_variant = rng.choice(COVER_VARIANTS)
        motif = rng.choice(MOTIFS)
        heading_style = rng.choice(HEADING_STYLES)

    toc_style = rng.choice(TOC_STYLES)

    content_len = len(plan.get("content_markdown") or "")
    density = "compact" if content_len > 4500 else rng.choice(["airy", "airy", "compact"])

    rounded = tone in _PLAYFUL_TONES or rng.random() < 0.35

    return DesignSpec(
        palette=palette,
        cover_variant=cover_variant,
        heading_style=heading_style,
        toc_style=toc_style,
        motif=motif,
        density=density,
        rounded=rounded,
        tone=tone,
        seed_tag=f"{palette.name}/{cover_variant}/{heading_style}",
    )
