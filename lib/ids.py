"""Small id/slug helpers shared by the Artists, Artworks, and Collections
pages. New ids only need to be unique (these are plain text primary keys,
not auto-increment or enum-constrained), so a suggestion here never has to
match the exact format of ids already in the database."""
import re
import secrets


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return text or "item"


def suggest_id(seed: str) -> str:
    return f"{slugify(seed)}-{secrets.token_hex(4)}"
