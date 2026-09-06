"""
Bulk importer matching the folder layout Json_handling.html already used:

    base_folder/
        artists/*.json        one artist record per file (artistId, name, ...)
        artworks/*.json       one artwork record per file (ArtworkID, title, ...)
        collections/*.json    one Week Best collection per file (collectionName, ArtworkIds, ...)
        images/               optional — <ArtworkID>.<ext>, used to fill in
                               featureImageUrl / colorAnalysis on an artwork
                               record that doesn't already have them.

Any of the four subfolders may be missing or empty — it's just skipped.
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from lib.color_analysis import analyze_image
from lib.config import PUBLIC_ARTWORK_IMAGE_BASE_URL, REMOTE_ARTWORK_IMAGE_FOLDER
from lib.db import add_artwork_to_collection, get_artwork, upsert_artist, upsert_artwork, upsert_collection
from lib.hostinger import upload_image

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]


@dataclass
class ImportPlan:
    artist_files: list[Path] = field(default_factory=list)
    artwork_files: list[Path] = field(default_factory=list)
    collection_files: list[Path] = field(default_factory=list)
    images_dir: Path | None = None
    errors: list[str] = field(default_factory=list)


def scan_folder(base_dir: str) -> ImportPlan:
    base = Path(base_dir)
    plan = ImportPlan()

    if not base.is_dir():
        plan.errors.append(f"Folder not found: {base_dir}")
        return plan

    artists_dir = base / "artists"
    artworks_dir = base / "artworks"
    collections_dir = base / "collections"
    images_dir = base / "images"

    if artists_dir.is_dir():
        plan.artist_files = sorted(artists_dir.glob("*.json"))
    if artworks_dir.is_dir():
        plan.artwork_files = sorted(artworks_dir.glob("*.json"))
    if collections_dir.is_dir():
        plan.collection_files = sorted(collections_dir.glob("*.json"))
    if images_dir.is_dir():
        plan.images_dir = images_dir

    if not (plan.artist_files or plan.artwork_files or plan.collection_files):
        plan.errors.append(
            "No artists/, artworks/, or collections/ subfolder with .json files was found in that folder."
        )

    return plan


def _find_local_image(images_dir: Path | None, artwork_id: str) -> Path | None:
    if images_dir is None:
        return None
    for ext in IMAGE_EXTENSIONS:
        candidate = images_dir / f"{artwork_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


def run_import(plan: ImportPlan, log) -> dict:
    """`log` is a callable taking one string — call it to report progress
    as the import runs (the page passes something that appends to a list
    and/or writes to the Streamlit UI)."""
    summary = {
        "artists_ok": 0, "artists_failed": 0,
        "artworks_ok": 0, "artworks_failed": 0,
        "collections_ok": 0, "collections_failed": 0,
    }

    for path in plan.artist_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            artist_id = upsert_artist(data)
            summary["artists_ok"] += 1
            log(f"✓ Artist: {path.name} → {artist_id}")
        except Exception as exc:  # noqa: BLE001
            summary["artists_failed"] += 1
            log(f"✗ Artist: {path.name} — {exc}")

    for path in plan.artwork_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            artwork_id = data.get("ArtworkID") or path.stem
            data["ArtworkID"] = artwork_id

            needs_image = not data.get("featureImageUrl")
            needs_colors = not data.get("colorAnalysis")
            if needs_image or needs_colors:
                local_image = _find_local_image(plan.images_dir, artwork_id)
                if local_image is not None:
                    image_bytes = local_image.read_bytes()
                    if needs_image:
                        data["featureImageUrl"] = upload_image(
                            Image.open(io.BytesIO(image_bytes)), REMOTE_ARTWORK_IMAGE_FOLDER,
                            PUBLIC_ARTWORK_IMAGE_BASE_URL, artwork_id,
                        )
                        log(f"   uploaded image for {artwork_id}")
                    if needs_colors:
                        data["colorAnalysis"] = analyze_image(io.BytesIO(image_bytes))["colorAnalysis"]
                        log(f"   generated colour analysis for {artwork_id}")

            artwork_id, colors_written = upsert_artwork(data)
            summary["artworks_ok"] += 1
            log(f"✓ Artwork: {path.name} → {artwork_id} ({colors_written} colour rows)")
        except Exception as exc:  # noqa: BLE001
            summary["artworks_failed"] += 1
            log(f"✗ Artwork: {path.name} — {exc}")

    for path in plan.collection_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            collection_id = upsert_collection(data)
            artwork_ids = data.get("ArtworkIds", [])
            linked, missing = 0, 0
            valid_ids = []
            for artwork_id in artwork_ids:
                if get_artwork(str(artwork_id)):
                    valid_ids.append(str(artwork_id))
                    linked += 1
                else:
                    missing += 1
            for artwork_id in valid_ids:
                add_artwork_to_collection(collection_id, artwork_id)
            summary["collections_ok"] += 1
            log(f"✓ Collection: {path.name} → {collection_id} (linked {linked}, missing {missing})")
        except Exception as exc:  # noqa: BLE001
            summary["collections_failed"] += 1
            log(f"✗ Collection: {path.name} — {exc}")

    return summary
