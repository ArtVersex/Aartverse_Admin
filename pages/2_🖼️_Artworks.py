from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_quill import st_quill

from lib.auth import logout_button, require_login
from lib.color_analysis import analyze_image
from lib.config import PUBLIC_ARTWORK_IMAGE_BASE_URL, REMOTE_ARTWORK_IMAGE_FOLDER
from lib.db import (
    delete_artwork,
    get_artwork,
    get_artwork_colors,
    get_distinct_categories,
    list_artists_for_picker,
    list_artworks,
    upsert_artwork,
)
from lib.hostinger import upload_image
from lib.ids import suggest_id
from lib.rich_text import RICH_TOOLBAR, normalize_html, plain_text_to_html

st.set_page_config(page_title="Artworks — Aartverse Admin", page_icon="🖼️", layout="wide")
require_login()
logout_button()

st.title("Artworks")

NONE_ARTIST_LABEL = "— none —"
NONE_CATEGORY_LABEL = "— choose or type below —"

# ============================================================
# LIST
# ============================================================
search = st.text_input("Search by title, artist, id, or category")
if "artwork_page" not in st.session_state:
    st.session_state.artwork_page = 1

result = list_artworks(search=search, page=st.session_state.artwork_page, page_size=20)
st.caption(f"{result['total']} artwork(s)")

if result["items"]:
    df = pd.DataFrame(result["items"])[["title", "artist_name", "category", "price", "in_stock", "artwork_id"]]
    st.dataframe(df, use_container_width=True, hide_index=True)

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← Previous", disabled=result["page"] <= 1):
            st.session_state.artwork_page -= 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<div style='text-align:center'>Page {result['page']} of {result['total_pages']}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next →", disabled=result["page"] >= result["total_pages"]):
            st.session_state.artwork_page += 1
            st.rerun()
else:
    st.info("No artworks found.")

st.divider()
mode = st.radio("Action", ["Add new artwork", "Edit / delete existing"], horizontal=True)

artists = list_artists_for_picker()
artist_options = {NONE_ARTIST_LABEL: ""}
for a in artists:
    artist_options[a["name"]] = a["artist_id"]
categories = get_distinct_categories()


def process_image(image_file, artwork_id: str):
    """Uploads the image to Hostinger (as WEBP) and runs the KMeans colour
    analysis on it. Returns (feature_image_url, color_analysis_dict)."""
    image_bytes = image_file.getvalue()
    with st.spinner("Uploading image to Hostinger…"):
        url = upload_image(
            Image.open(io.BytesIO(image_bytes)), REMOTE_ARTWORK_IMAGE_FOLDER,
            PUBLIC_ARTWORK_IMAGE_BASE_URL, artwork_id,
        )
    with st.spinner("Analyzing colours…"):
        analysis = analyze_image(io.BytesIO(image_bytes))["colorAnalysis"]
    return url, analysis


def rich_field(label: str, current_value: str | None, key: str, help_text: str | None = None) -> str:
    """One WYSIWYG editor (bold / italic / lists / colour / highlight —
    matches AartVerse_v1's .richtext rendering) for a single narrative
    field. Returns the current HTML content, exactly as typed."""
    st.markdown(f"**{label}**")
    if help_text:
        st.caption(help_text)
    return st_quill(
        value=plain_text_to_html(current_value),
        html=True,
        toolbar=RICH_TOOLBAR,
        key=key,
    )


def artwork_fields_form(defaults: dict | None, key_prefix: str):
    """Renders the shared set of artwork fields. `defaults` is a DB row
    (dict) when editing, or None when adding. Returns a dict of raw
    widget values (not yet normalized to DB types)."""
    d = defaults or {}
    values = {}
    values["title"] = st.text_input("Title", value=d.get("title", ""), key=f"{key_prefix}_title")

    artist_names = list(artist_options.keys())
    current_artist_name = NONE_ARTIST_LABEL
    for name, aid in artist_options.items():
        if aid and aid == d.get("artist_id"):
            current_artist_name = name
    values["artist_choice"] = st.selectbox(
        "Artist", artist_names, index=artist_names.index(current_artist_name), key=f"{key_prefix}_artist"
    )
    values["artist_name_override"] = st.text_input(
        "Artist name (display text)", value=d.get("artist_name", "") or "", key=f"{key_prefix}_artist_name"
    )

    cat_choices = [NONE_CATEGORY_LABEL] + categories
    current_category = d.get("category") or NONE_CATEGORY_LABEL
    cat_index = cat_choices.index(current_category) if current_category in cat_choices else 0
    values["category"] = st.selectbox("Category", cat_choices, index=cat_index, key=f"{key_prefix}_category")
    values["category_custom"] = st.text_input(
        "Or type a new category", key=f"{key_prefix}_category_custom",
        help="Takes priority over the dropdown above if filled in.",
    )
    values["subcategory"] = st.text_input("Subcategory", value=d.get("subcategory", "") or "", key=f"{key_prefix}_subcat")

    col1, col2, col3 = st.columns(3)
    with col1:
        values["price"] = st.number_input(
            "Price (₹)", min_value=0.0, step=100.0,
            value=float(d["price"]) if d.get("price") is not None else 0.0, key=f"{key_prefix}_price",
        )
    with col2:
        values["year"] = st.number_input(
            "Year", min_value=0, max_value=2100, step=1,
            value=int(d["year"]) if d.get("year") else 2026, key=f"{key_prefix}_year",
        )
    with col3:
        values["dimensions"] = st.text_input("Dimensions", value=d.get("dimensions", "") or "", key=f"{key_prefix}_dim")

    values["place"] = st.text_input("Place", value=d.get("place", "") or "", key=f"{key_prefix}_place")
    values["certificate_number"] = st.text_input(
        "Certificate number", value=d.get("certificate_number", "") or "", key=f"{key_prefix}_cert"
    )

    values["feature_image_url"] = st.text_input(
        "Feature image URL", value=d.get("feature_image_url", "") or "", key=f"{key_prefix}_image_url",
        help="Paste a URL directly, or upload an image below (which replaces this and regenerates the colour analysis).",
    )
    if d.get("feature_image_url"):
        st.image(d["feature_image_url"], width=220, caption="Current image")
    values["image_file"] = st.file_uploader(
        "Upload image (uploads to Hostinger + auto-generates colour analysis)",
        type=["jpg", "jpeg", "png", "webp"], key=f"{key_prefix}_image_upload",
    )

    col4, col5, col6 = st.columns(3)
    with col4:
        values["in_stock"] = st.checkbox("In stock", value=d.get("in_stock", 1) != 0, key=f"{key_prefix}_instock")
    with col5:
        values["impactful"] = st.checkbox(
            "Impactful (shown on browsing pages)", value=d.get("impactful") == 1, key=f"{key_prefix}_impactful"
        )
    with col6:
        values["part_of_collection"] = st.checkbox(
            "Part of an artist collection/series", value=d.get("part_of_collection") == 1, key=f"{key_prefix}_poc"
        )
    values["collection_name"] = st.text_input(
        "Collection / series name", value=d.get("collection_name", "") or "", key=f"{key_prefix}_collname",
        help="The artist's own series name — not a Week Best collection (manage those under Collections).",
    )

    st.divider()
    st.caption(
        "The fields below support rich formatting — bold, italic, headings, bulleted/numbered lists, "
        "text colour, and highlight. AartVerse_v1 already renders this formatting on the artwork page, "
        "so no other changes are needed for it to show up."
    )
    values["short_description"] = rich_field(
        "Short description", d.get("short_description"), f"{key_prefix}_short_quill",
    )
    values["description"] = rich_field("Description", d.get("description"), f"{key_prefix}_desc_quill")
    values["technique_highlight"] = rich_field(
        "Technique highlight", d.get("technique_highlight"), f"{key_prefix}_tech_quill"
    )
    values["historical_context"] = rich_field(
        "Historical context", d.get("historical_context"), f"{key_prefix}_hist_quill"
    )
    values["symbolism"] = rich_field("Symbolism", d.get("symbolism"), f"{key_prefix}_symb_quill")
    values["composition_analysis"] = rich_field(
        "Composition analysis", d.get("composition_analysis"), f"{key_prefix}_comp_quill"
    )
    values["cultural_significance"] = rich_field(
        "Cultural significance", d.get("cultural_significance"), f"{key_prefix}_cult_quill"
    )

    return values


def build_data_dict(artwork_id: str, values: dict, feature_image_url: str, color_analysis) -> dict:
    final_category = values["category_custom"].strip() or (
        values["category"] if values["category"] != NONE_CATEGORY_LABEL else ""
    )
    artist_id = artist_options.get(values["artist_choice"], "")
    artist_display_name = values["artist_name_override"] or (
        values["artist_choice"] if values["artist_choice"] != NONE_ARTIST_LABEL else ""
    )
    return {
        "ArtworkID": artwork_id,
        "title": values["title"],
        "artistId": artist_id or None,
        "ArtistName": artist_display_name or None,
        "category": final_category or None,
        "subcategory": values["subcategory"] or None,
        "price": values["price"] or None,
        "year": int(values["year"]) if values["year"] else None,
        "InStock": values["in_stock"],
        "Place": values["place"] or None,
        "Impactful": values["impactful"],
        "PartOfCollection": values["part_of_collection"],
        "CollectionName": values["collection_name"] or None,
        "certificateNumber": values["certificate_number"] or None,
        "dimensions": values["dimensions"] or None,
        "featureImageUrl": feature_image_url or None,
        "shortDescription": normalize_html(values["short_description"]),
        "description": normalize_html(values["description"]),
        "techniqueHighlight": normalize_html(values["technique_highlight"]),
        "historicalContext": normalize_html(values["historical_context"]),
        "Symbolism": normalize_html(values["symbolism"]),
        "compositionAnalysis": normalize_html(values["composition_analysis"]),
        "culturalSignificance": normalize_html(values["cultural_significance"]),
        "colorAnalysis": color_analysis,
    }


# ============================================================
# ADD
# ============================================================
if mode == "Add new artwork":
    st.subheader("Add artwork")
    artwork_id_input = st.text_input("Artwork ID (leave blank to auto-generate)")
    values = artwork_fields_form(None, "add")
    submitted = st.button("Create artwork", type="primary")

    if submitted:
        if not values["title"]:
            st.error("Title is required.")
        else:
            final_id = artwork_id_input.strip() or suggest_id(values["title"])
            feature_image_url = values["feature_image_url"]
            color_analysis = None
            if values["image_file"] is not None:
                try:
                    feature_image_url, color_analysis = process_image(values["image_file"], final_id)
                except Exception as exc:
                    st.error(f"Image processing failed: {exc}")
                    st.stop()

            data = build_data_dict(final_id, values, feature_image_url, color_analysis)
            try:
                artwork_id, colors_written = upsert_artwork(data)
                st.success(f"Artwork '{values['title']}' created (id: {artwork_id}). {colors_written} colour rows written.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

# ============================================================
# EDIT / DELETE
# ============================================================
else:
    if not result["items"] and not search:
        st.info("No artworks to edit yet.")
    else:
        all_for_picker = list_artworks(search=search, page=1, page_size=100)["items"]
        options = {f"{a['title']} ({a['artwork_id']})": a["artwork_id"] for a in all_for_picker}
        if not options:
            st.info("No matching artworks.")
        else:
            choice = st.selectbox("Choose an artwork", list(options.keys()))
            artwork_id = options[choice]
            artwork = get_artwork(artwork_id)

            st.subheader(f"Edit {artwork['title']}")
            values = artwork_fields_form(artwork, "edit")
            save = st.button("Save changes", type="primary")

            if save:
                feature_image_url = values["feature_image_url"]
                color_analysis = None
                keep_existing_colors = True
                if values["image_file"] is not None:
                    try:
                        feature_image_url, color_analysis = process_image(values["image_file"], artwork_id)
                        keep_existing_colors = False
                    except Exception as exc:
                        st.error(f"Image processing failed: {exc}")
                        st.stop()

                if keep_existing_colors:
                    # No new image uploaded — keep the existing colour
                    # analysis exactly as it is rather than wiping it out.
                    existing = get_artwork(artwork_id)
                    raw = existing.get("color_analysis")
                    if raw:
                        import json as _json
                        try:
                            color_analysis = _json.loads(raw)
                        except (TypeError, ValueError):
                            color_analysis = None

                data = build_data_dict(artwork_id, values, feature_image_url, color_analysis)
                try:
                    upsert_artwork(data)
                    st.success("Saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")

            with st.expander("View stored colour analysis"):
                colors = get_artwork_colors(artwork_id)
                if colors:
                    st.dataframe(pd.DataFrame(colors), use_container_width=True, hide_index=True)
                else:
                    st.caption("No colour analysis stored for this artwork yet.")

            st.divider()
            st.subheader("Delete this artwork")
            st.caption("This also removes its colour analysis rows and its membership in any Week Best collection.")
            confirm = st.checkbox(
                f"I understand this will permanently delete \"{artwork['title']}\".", key="confirm_delete_artwork"
            )
            if st.button("Delete artwork", disabled=not confirm):
                delete_artwork(artwork_id)
                st.success("Deleted.")
                st.rerun()
