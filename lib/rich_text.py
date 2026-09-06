"""
Helpers for the rich-text fields on an artwork — short description,
description, technique highlight, historical context, symbolism,
composition analysis, cultural significance.

AartVerse_v1 (the public site) already renders these as real formatted
HTML whenever they look like markup (see lib/utils.ts#looksLikeHtml and
#sanitizeRichText, applied in app/artworks/[artwork_id]/page.tsx's
RichText/Narrative components) and falls back to plain text otherwise. So
the WYSIWYG editor here only needs to produce clean HTML — the site needs
no changes at all to display it formatted.
"""
from __future__ import annotations

import re

# Quill's own "nothing typed" output — treated as empty rather than saved
# as a value.
_EMPTY_QUILL_HTML = {"", "<p></p>", "<p><br></p>"}

# Toolbar shared by every rich-text field: headings, the requested bold /
# lists / highlight / colourful text, plus a few natural companions
# (italic, underline, links, blockquotes) that AartVerse_v1's .richtext
# CSS already has rules for.
RICH_TOOLBAR = [
    [{"header": [1, 2, 3, False]}],
    ["bold", "italic", "underline", "strike"],
    [{"color": []}, {"background": []}],
    [{"list": "ordered"}, {"list": "bullet"}],
    ["blockquote", "link"],
    ["clean"],
]


def plain_text_to_html(text: str | None) -> str:
    """Seeds the editor when a field currently holds plain text (no
    markup yet) — wraps it in <p> tags so existing paragraph breaks
    survive instead of collapsing onto one line the first time it's
    opened in the editor. Content that already looks like HTML is left
    untouched."""
    if not text:
        return ""
    if "<" in text and ">" in text:
        return text
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return ""
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def normalize_html(html: str | None) -> str | None:
    """Cleans up what the editor hands back before saving — Quill's
    "empty" output isn't an empty string, so treat its known empty forms
    as None rather than storing them as real content."""
    if html is None:
        return None
    stripped = html.strip()
    return None if stripped in _EMPTY_QUILL_HTML else stripped
