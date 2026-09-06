"""
Central place every other module reads settings from. Nothing here is
hard-coded — it's all read from environment variables, loaded from a local
.env file (see .env.example) via python-dotenv so `streamlit run app.py`
just works without exporting shell variables by hand.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


# ----------------------------------------------------------------------
# Database — the SAME MariaDB/MySQL database AartVerse_v1 (the public
# site) reads from. This app is the only place meant to write to it.
# ----------------------------------------------------------------------
DB_HOST = _env("DB_HOST")
DB_PORT = int(_env("DB_PORT", "3306"))
DB_NAME = _env("DB_NAME")
DB_USER = _env("DB_USER")
DB_PASSWORD = _env("DB_PASSWORD")

# ----------------------------------------------------------------------
# Hostinger SFTP — where artwork/artist images are uploaded.
# ----------------------------------------------------------------------
SFTP_HOST = _env("SFTP_HOST")
SFTP_PORT = int(_env("SFTP_PORT", "22"))
SFTP_USERNAME = _env("SFTP_USERNAME")
SFTP_PASSWORD = _env("SFTP_PASSWORD")

REMOTE_ARTWORK_IMAGE_FOLDER = _env(
    "REMOTE_ARTWORK_IMAGE_FOLDER",
    "domains/springgreen-antelope-607895.hostingersite.com/public_html/images/artworks",
)
PUBLIC_ARTWORK_IMAGE_BASE_URL = _env(
    "PUBLIC_ARTWORK_IMAGE_BASE_URL",
    "https://springgreen-antelope-607895.hostingersite.com/images/artworks",
)
REMOTE_ARTIST_IMAGE_FOLDER = _env(
    "REMOTE_ARTIST_IMAGE_FOLDER",
    "domains/springgreen-antelope-607895.hostingersite.com/public_html/images/artists",
)
PUBLIC_ARTIST_IMAGE_BASE_URL = _env(
    "PUBLIC_ARTIST_IMAGE_BASE_URL",
    "https://springgreen-antelope-607895.hostingersite.com/images/artists",
)

# ----------------------------------------------------------------------
# Admin password gate
# ----------------------------------------------------------------------
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")

CATEGORY_MAP = {
    "E8BZZyQWmCA0rW7z4gaH": "Collage",
    "IL4znyS0vjqu9jHRxhoM": "Drawing",
    "L8pXp9ozGp3O4SP6sc4I": "Digital Painting",
    "RchEX0Y59bTwaYjkDvtH": "Print Making",
    "a6gv0FHlDZGxY6fNfdL2": "Painting",
}
