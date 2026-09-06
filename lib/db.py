"""
All SQL lives here — one function per operation, all parameterized. The
schema mirrors AartVerse_v1's tables exactly (artists, artworks,
artwork_colors, week_best_collections, week_best_collection_artworks).

Field-naming convention: every function that reads/writes a full artist,
artwork, or collection record uses the SAME camelCase/PascalCase JSON key
names as the existing export pipeline in Json_handling.html (e.g.
"ArtworkID", "artistId", "InStock", "PartOfCollection", "colorAnalysis").
That keeps this app able to read the JSON files your notebook already
produces, and the single-record UI forms build the exact same shape of
dict before calling these functions — one write path for both.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import mysql.connector

from lib.config import CATEGORY_MAP, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


# ============================================================
# CONNECTION
# ============================================================

@contextmanager
def get_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=False,
        connection_timeout=15,
    )
    try:
        yield conn
    finally:
        conn.close()


def test_connection() -> tuple[bool, str]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
        return True, f"Connected — MariaDB/MySQL {version}"
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as-is
        return False, str(exc)


# ============================================================
# GENERAL HELPERS (ported from Json_handling.html)
# ============================================================

def as_text(value):
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def as_bool(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"yes", "true", "1", "y", "on"}


def as_int(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def as_decimal(value):
    if value is None:
        return None
    text = re.sub(r"[^\d.\-]", "", str(value).strip())
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_datetime(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def parse_date(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def json_text(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def clean_db_text(value, max_length):
    if value is None:
        return None
    value = str(value)
    return value[:max_length] if len(value) > max_length else value


def parse_rgb(value):
    if value is None:
        return None, None, None
    if isinstance(value, dict):
        r, g, b = value.get("r"), value.get("g"), value.get("b")
        if r is not None and g is not None and b is not None:
            try:
                return int(r), int(g), int(b)
            except (ValueError, TypeError):
                return None, None, None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return int(value[0]), int(value[1]), int(value[2])
        except (ValueError, TypeError):
            return None, None, None
    if isinstance(value, str):
        numbers = re.findall(r"\d+", value)
        if len(numbers) >= 3:
            try:
                return int(numbers[0]), int(numbers[1]), int(numbers[2])
            except ValueError:
                pass
    return None, None, None


def clean_hex(value):
    if value is None:
        return None
    value = str(value).strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return value
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return "#" + value
    return None


def color_proportion(value) -> Decimal:
    if value is None:
        return Decimal("0.000")
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.000")


def make_week_best_collection_id(collection_name, artist_id, week_of) -> str:
    source = f"{artist_id or ''}|{week_of or ''}|{collection_name or ''}".lower()
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:24]
    return "wbc_" + digest


# ============================================================
# ARTISTS
# ============================================================

def list_artists(search: str | None = None) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        if search and search.strip():
            like = f"%{search.strip()}%"
            cursor.execute(
                "SELECT * FROM artists WHERE name LIKE %s OR slug LIKE %s OR artist_id LIKE %s ORDER BY name ASC",
                (like, like, like),
            )
        else:
            cursor.execute("SELECT * FROM artists ORDER BY name ASC")
        rows = cursor.fetchall()
        cursor.close()
    return rows


def get_artist(artist_id: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM artists WHERE artist_id = %s LIMIT 1", (artist_id,))
        row = cursor.fetchone()
        cursor.close()
    return row


def list_artists_for_picker() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT artist_id, name FROM artists ORDER BY name ASC")
        rows = cursor.fetchall()
        cursor.close()
    return rows


def count_artists() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM artists")
        total = cursor.fetchone()[0]
        cursor.close()
    return total


def upsert_artist(data: dict) -> str:
    """`data` uses the same keys as an Artist_JSON file: artistId, name,
    slug, artistStatement, profileImageUrl, coverImageUrl, location,
    mediums (list or string), website, instagram, featured, active."""
    artist_id = as_text(data.get("artistId"))
    if not artist_id:
        raise ValueError("artistId is required.")

    name = as_text(data.get("name")) or artist_id
    mediums = data.get("mediums")
    if isinstance(mediums, list):
        mediums = json.dumps(mediums, ensure_ascii=False)
    else:
        mediums = as_text(mediums)

    sql = """
        INSERT INTO artists (
            artist_id, name, slug, artist_statement, profile_image_url,
            cover_image_url, location, mediums, website, instagram, featured, active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name), slug = VALUES(slug), artist_statement = VALUES(artist_statement),
            profile_image_url = VALUES(profile_image_url), cover_image_url = VALUES(cover_image_url),
            location = VALUES(location), mediums = VALUES(mediums), website = VALUES(website),
            instagram = VALUES(instagram), featured = VALUES(featured), active = VALUES(active)
    """
    values = (
        artist_id, name, as_text(data.get("slug")), as_text(data.get("artistStatement")),
        as_text(data.get("profileImageUrl")), as_text(data.get("coverImageUrl")),
        as_text(data.get("location")), mediums, as_text(data.get("website")),
        as_text(data.get("instagram")), as_bool(data.get("featured")), as_bool(data.get("active")),
    )

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        cursor.close()
    return artist_id


def delete_artist(artist_id: str) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM artworks WHERE artist_id = %s", (artist_id,))
        linked = cursor.fetchone()[0]
        if linked > 0:
            cursor.close()
            return {"deleted": False, "blocked_by_artwork_count": linked}
        cursor.execute("DELETE FROM artists WHERE artist_id = %s", (artist_id,))
        conn.commit()
        cursor.close()
    return {"deleted": True}


# ============================================================
# ARTWORKS
# ============================================================

def list_artworks(search: str | None = None, artist_id: str | None = None,
                   page: int = 1, page_size: int = 25) -> dict:
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    clauses, params = [], []
    if search and search.strip():
        like = f"%{search.strip()}%"
        clauses.append("(w.title LIKE %s OR w.artist_name LIKE %s OR w.artwork_id LIKE %s OR w.category LIKE %s)")
        params += [like, like, like, like]
    if artist_id:
        clauses.append("w.artist_id = %s")
        params.append(artist_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""SELECT w.*, a.slug AS artist_slug FROM artworks w
                LEFT JOIN artists a ON a.artist_id = w.artist_id
                {where_sql} ORDER BY w.created_at DESC, w.artwork_id DESC
                LIMIT %s OFFSET %s""",
            (*params, page_size, offset),
        )
        items = cursor.fetchall()
        cursor.execute(f"SELECT COUNT(*) AS total FROM artworks w {where_sql}", params)
        total = cursor.fetchone()["total"]
        cursor.close()

    total_pages = max(1, -(-total // page_size))
    return {"items": items, "page": page, "page_size": page_size, "total": total, "total_pages": total_pages}


def get_artwork(artwork_id: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM artworks WHERE artwork_id = %s LIMIT 1", (artwork_id,))
        row = cursor.fetchone()
        cursor.close()
    return row


def get_artwork_colors(artwork_id: str) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM artwork_colors WHERE artwork_id = %s ORDER BY color_scope ASC, rank_number ASC",
            (artwork_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    return rows


def list_artworks_for_picker() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT artwork_id, title, artist_name FROM artworks ORDER BY title ASC")
        rows = cursor.fetchall()
        cursor.close()
    return rows


def get_distinct_categories() -> list[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category FROM artworks WHERE category IS NOT NULL AND category != '' ORDER BY category ASC"
        )
        rows = [r[0] for r in cursor.fetchall()]
        cursor.close()
    return rows


def count_artworks() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM artworks")
        total = cursor.fetchone()[0]
        cursor.close()
    return total


def _import_artwork_colors(cursor, artwork_id: str, color_analysis) -> int:
    cursor.execute("DELETE FROM artwork_colors WHERE artwork_id = %s", (artwork_id,))
    if not isinstance(color_analysis, dict):
        return 0

    count = 0
    color_families = color_analysis.get("colorFamilies", {})
    if isinstance(color_families, dict):
        for family, proportion in color_families.items():
            cursor.execute(
                """INSERT INTO artwork_colors
                   (artwork_id, color_name, color_family, color_scope, hex, proportion, rank_number, rgb_r, rgb_g, rgb_b)
                   VALUES (%s, %s, %s, 'family', NULL, %s, NULL, NULL, NULL, NULL)""",
                (artwork_id, clean_db_text(family, 60), clean_db_text(family, 60), color_proportion(proportion)),
            )
            count += 1

    dominant_colors = color_analysis.get("dominantColors", [])
    if isinstance(dominant_colors, list):
        for index, color in enumerate(dominant_colors):
            if not isinstance(color, dict):
                continue
            name = color.get("name") or color.get("colorName") or color.get("color") or ""
            family = color.get("family") or color.get("colorFamily") or ""
            hex_value = clean_hex(color.get("hex"))
            rank = color.get("rank") or color.get("rankNumber") or index + 1
            r, g, b = parse_rgb(color.get("rgb"))
            proportion = color_proportion(color.get("proportion"))
            cursor.execute(
                """INSERT INTO artwork_colors
                   (artwork_id, color_name, color_family, color_scope, hex, proportion, rank_number, rgb_r, rgb_g, rgb_b)
                   VALUES (%s, %s, %s, 'dominant', %s, %s, %s, %s, %s, %s)""",
                (artwork_id, clean_db_text(name, 60), clean_db_text(family, 60), hex_value, proportion, as_int(rank), r, g, b),
            )
            count += 1
    return count


def upsert_artwork(data: dict) -> tuple[str, int]:
    """`data` uses the same keys as an artwork JSON file: ArtworkID, title,
    artistId, ArtistName, category / categoryID, subcategory, price, year,
    InStock, Place, Impactful, PartOfCollection, CollectionName,
    certificateNumber, dimensions, featureImageUrl, shortDescription,
    description, techniqueHighlight, historicalContext, Symbolism,
    compositionAnalysis, culturalSignificance, timestampcreate,
    colorAnalysis. Returns (artwork_id, color_rows_written)."""
    artwork_id = as_text(data.get("ArtworkID"))
    if not artwork_id:
        raise ValueError("ArtworkID is required.")

    artist_id = as_text(data.get("artistId"))
    artist_name = as_text(data.get("ArtistName"))
    category_id = as_text(data.get("categoryID"))
    category = as_text(data.get("category")) or CATEGORY_MAP.get(category_id, "Other")
    title = as_text(data.get("title")) or artwork_id

    sql = """
        INSERT INTO artworks (
            artwork_id, title, artist_id, artist_name, category, category_id, subcategory,
            price, year, in_stock, place, impactful, part_of_collection, collection_name,
            certificate_number, dimensions, feature_image_url, short_description, description,
            technique_highlight, historical_context, symbolism, composition_analysis,
            cultural_significance, timestamp_create, color_analysis
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title), artist_id = VALUES(artist_id), artist_name = VALUES(artist_name),
            category = VALUES(category), category_id = VALUES(category_id), subcategory = VALUES(subcategory),
            price = VALUES(price), year = VALUES(year), in_stock = VALUES(in_stock), place = VALUES(place),
            impactful = VALUES(impactful), part_of_collection = VALUES(part_of_collection),
            collection_name = VALUES(collection_name), certificate_number = VALUES(certificate_number),
            dimensions = VALUES(dimensions), feature_image_url = VALUES(feature_image_url),
            short_description = VALUES(short_description), description = VALUES(description),
            technique_highlight = VALUES(technique_highlight), historical_context = VALUES(historical_context),
            symbolism = VALUES(symbolism), composition_analysis = VALUES(composition_analysis),
            cultural_significance = VALUES(cultural_significance), timestamp_create = VALUES(timestamp_create),
            color_analysis = VALUES(color_analysis)
    """
    color_analysis = data.get("colorAnalysis")
    values = (
        artwork_id, title, artist_id, artist_name, category, category_id,
        as_text(data.get("subcategory")), as_decimal(data.get("price")), as_int(data.get("year")),
        as_bool(data.get("InStock")), as_text(data.get("Place")), as_bool(data.get("Impactful")),
        as_bool(data.get("PartOfCollection")), as_text(data.get("CollectionName")),
        as_text(data.get("certificateNumber")), as_text(data.get("dimensions")),
        as_text(data.get("featureImageUrl")), as_text(data.get("shortDescription")),
        as_text(data.get("description")), as_text(data.get("techniqueHighlight")),
        as_text(data.get("historicalContext")), as_text(data.get("Symbolism")),
        as_text(data.get("compositionAnalysis")), as_text(data.get("culturalSignificance")),
        parse_datetime(data.get("timestampcreate")), json_text(color_analysis),
    )

    with get_connection() as conn:
        cursor = conn.cursor()
        if artist_id:
            cursor.execute("SELECT 1 FROM artists WHERE artist_id = %s", (artist_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO artists (artist_id, name, slug) VALUES (%s, %s, NULL)",
                    (artist_id, artist_name or artist_id),
                )
        cursor.execute(sql, values)
        colors_written = _import_artwork_colors(cursor, artwork_id, color_analysis)
        conn.commit()
        cursor.close()
    return artwork_id, colors_written


def delete_artwork(artwork_id: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM artwork_colors WHERE artwork_id = %s", (artwork_id,))
        cursor.execute("DELETE FROM week_best_collection_artworks WHERE artwork_id = %s", (artwork_id,))
        cursor.execute("DELETE FROM artworks WHERE artwork_id = %s", (artwork_id,))
        conn.commit()
        cursor.close()


# ============================================================
# WEEK BEST COLLECTIONS
# ============================================================

def list_collections() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM week_best_collections ORDER BY week_of DESC, created_at DESC")
        rows = cursor.fetchall()
        cursor.close()
    return rows


def count_collections() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM week_best_collections")
        total = cursor.fetchone()[0]
        cursor.close()
    return total


def get_collection(collection_id: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM week_best_collections WHERE week_best_collection_id = %s LIMIT 1", (collection_id,)
        )
        row = cursor.fetchone()
        cursor.close()
    return row


def get_collection_artworks(collection_id: str) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT w.artwork_id, w.title, w.artist_name, wbca.sort_order
               FROM week_best_collection_artworks wbca
               JOIN artworks w ON w.artwork_id = wbca.artwork_id
               WHERE wbca.week_best_collection_id = %s
               ORDER BY wbca.sort_order ASC""",
            (collection_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    return rows


def upsert_collection(data: dict, existing_id: str | None = None) -> str:
    """`data` uses the same keys as a collection JSON file: collectionName,
    artistId, weekOf, label, headline. If `existing_id` is given (editing),
    that id is kept; otherwise a new id is deterministically derived from
    collectionName + artistId + weekOf, matching Json_handling.html."""
    collection_name = as_text(data.get("collectionName"))
    if not collection_name:
        raise ValueError("collectionName is required.")
    artist_id = as_text(data.get("artistId"))
    week_of = parse_date(data.get("weekOf"))
    label = as_text(data.get("label"))
    headline = as_text(data.get("headline"))

    collection_id = existing_id or make_week_best_collection_id(collection_name, artist_id, week_of)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO week_best_collections
               (week_best_collection_id, collection_name, artist_id, week_of, label, headline)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                   collection_name = VALUES(collection_name), artist_id = VALUES(artist_id),
                   week_of = VALUES(week_of), label = VALUES(label), headline = VALUES(headline)""",
            (collection_id, collection_name, artist_id, week_of, label, headline),
        )
        conn.commit()
        cursor.close()
    return collection_id


def delete_collection(collection_id: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM week_best_collection_artworks WHERE week_best_collection_id = %s", (collection_id,))
        cursor.execute("DELETE FROM week_best_collections WHERE week_best_collection_id = %s", (collection_id,))
        conn.commit()
        cursor.close()


def add_artwork_to_collection(collection_id: str, artwork_id: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM week_best_collection_artworks WHERE week_best_collection_id = %s AND artwork_id = %s",
            (collection_id, artwork_id),
        )
        if cursor.fetchone():
            cursor.close()
            return
        cursor.execute(
            "SELECT MAX(sort_order) FROM week_best_collection_artworks WHERE week_best_collection_id = %s",
            (collection_id,),
        )
        max_order = cursor.fetchone()[0]
        next_order = (max_order if max_order is not None else -1) + 1
        cursor.execute(
            "INSERT INTO week_best_collection_artworks (week_best_collection_id, artwork_id, sort_order) VALUES (%s, %s, %s)",
            (collection_id, artwork_id, next_order),
        )
        conn.commit()
        cursor.close()


def set_collection_artworks(collection_id: str, ordered_artwork_ids: list[str]) -> None:
    """Replaces the full membership list in the given order (sort_order =
    list index) — used by the "save order / remove" editor, matching the
    delete-then-reinsert pattern Json_handling.html already uses."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM week_best_collection_artworks WHERE week_best_collection_id = %s", (collection_id,))
        for sort_order, artwork_id in enumerate(ordered_artwork_ids):
            cursor.execute(
                "INSERT INTO week_best_collection_artworks (week_best_collection_id, artwork_id, sort_order) VALUES (%s, %s, %s)",
                (collection_id, artwork_id, sort_order),
            )
        conn.commit()
        cursor.close()
