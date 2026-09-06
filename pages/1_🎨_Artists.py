import json

import pandas as pd
import streamlit as st
from PIL import Image

from lib.auth import logout_button, require_login
from lib.config import PUBLIC_ARTIST_IMAGE_BASE_URL, REMOTE_ARTIST_IMAGE_FOLDER
from lib.db import delete_artist, get_artist, list_artists, upsert_artist
from lib.hostinger import upload_image
from lib.ids import slugify, suggest_id

st.set_page_config(page_title="Artists — Aartverse Admin", page_icon="🎨", layout="wide")
require_login()
logout_button()

st.title("Artists")


def mediums_to_string(raw) -> str:
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return ", ".join(parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    return str(raw)


search = st.text_input("Search by name, slug, or id")
artists = list_artists(search)
st.caption(f"{len(artists)} artist(s)")

if artists:
    df = pd.DataFrame(artists)[["name", "slug", "location", "featured", "active", "artist_id"]]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No artists found.")

st.divider()
mode = st.radio("Action", ["Add new artist", "Edit / delete existing"], horizontal=True)

# ============================================================
# ADD
# ============================================================
if mode == "Add new artist":
    st.subheader("Add artist")
    with st.form("add_artist_form"):
        name = st.text_input("Name")
        artist_id_input = st.text_input(
            "Artist ID (leave blank to auto-generate)",
            help="Plain unique text id — any value works as long as it's unique.",
        )
        slug_input = st.text_input("Slug (leave blank to auto-generate from name)")
        artist_statement = st.text_area("Artist statement")

        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input("Location")
            website = st.text_input("Website")
            profile_image_file = st.file_uploader(
                "Profile image (uploads to Hostinger)", type=["jpg", "jpeg", "png", "webp"], key="add_profile"
            )
        with col2:
            mediums = st.text_input("Mediums (comma separated)")
            instagram = st.text_input("Instagram")
            cover_image_file = st.file_uploader(
                "Cover image (uploads to Hostinger)", type=["jpg", "jpeg", "png", "webp"], key="add_cover"
            )

        featured = st.checkbox("Featured")
        active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Create artist", type="primary")

    if submitted:
        if not name:
            st.error("Name is required.")
        else:
            final_id = artist_id_input.strip() or suggest_id(name)
            final_slug = slug_input.strip() or slugify(name)

            profile_url = ""
            cover_url = ""
            try:
                with st.spinner("Uploading images to Hostinger…"):
                    if profile_image_file is not None:
                        profile_url = upload_image(
                            Image.open(profile_image_file), REMOTE_ARTIST_IMAGE_FOLDER,
                            PUBLIC_ARTIST_IMAGE_BASE_URL, f"{final_id}-profile",
                        )
                    if cover_image_file is not None:
                        cover_url = upload_image(
                            Image.open(cover_image_file), REMOTE_ARTIST_IMAGE_FOLDER,
                            PUBLIC_ARTIST_IMAGE_BASE_URL, f"{final_id}-cover",
                        )
            except Exception as exc:
                st.error(f"Image upload failed: {exc}")
                st.stop()

            data = {
                "artistId": final_id, "name": name, "slug": final_slug,
                "artistStatement": artist_statement, "profileImageUrl": profile_url,
                "coverImageUrl": cover_url, "location": location,
                "mediums": [m.strip() for m in mediums.split(",") if m.strip()],
                "website": website, "instagram": instagram,
                "featured": featured, "active": active,
            }
            try:
                upsert_artist(data)
                st.success(f"Artist '{name}' created (id: {final_id}).")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

# ============================================================
# EDIT / DELETE
# ============================================================
else:
    if not artists:
        st.info("No artists to edit yet.")
    else:
        options = {f"{a['name']} ({a['artist_id']})": a["artist_id"] for a in artists}
        choice = st.selectbox("Choose an artist", list(options.keys()))
        artist_id = options[choice]
        artist = get_artist(artist_id)

        st.subheader(f"Edit {artist['name']}")
        with st.form("edit_artist_form"):
            name = st.text_input("Name", value=artist["name"])
            slug = st.text_input("Slug", value=artist["slug"] or "")
            artist_statement = st.text_area("Artist statement", value=artist["artist_statement"] or "")

            col1, col2 = st.columns(2)
            with col1:
                location = st.text_input("Location", value=artist["location"] or "")
                website = st.text_input("Website", value=artist["website"] or "")
                if artist["profile_image_url"]:
                    st.image(artist["profile_image_url"], width=120, caption="Current profile image")
                profile_image_file = st.file_uploader(
                    "Replace profile image", type=["jpg", "jpeg", "png", "webp"], key="edit_profile"
                )
            with col2:
                mediums = st.text_input("Mediums (comma separated)", value=mediums_to_string(artist["mediums"]))
                instagram = st.text_input("Instagram", value=artist["instagram"] or "")
                if artist["cover_image_url"]:
                    st.image(artist["cover_image_url"], width=220, caption="Current cover image")
                cover_image_file = st.file_uploader(
                    "Replace cover image", type=["jpg", "jpeg", "png", "webp"], key="edit_cover"
                )

            featured = st.checkbox("Featured", value=artist["featured"] == 1)
            active = st.checkbox("Active", value=artist["active"] != 0)
            save = st.form_submit_button("Save changes", type="primary")

        if save:
            profile_url = artist["profile_image_url"]
            cover_url = artist["cover_image_url"]
            try:
                with st.spinner("Uploading images to Hostinger…"):
                    if profile_image_file is not None:
                        profile_url = upload_image(
                            Image.open(profile_image_file), REMOTE_ARTIST_IMAGE_FOLDER,
                            PUBLIC_ARTIST_IMAGE_BASE_URL, f"{artist_id}-profile",
                        )
                    if cover_image_file is not None:
                        cover_url = upload_image(
                            Image.open(cover_image_file), REMOTE_ARTIST_IMAGE_FOLDER,
                            PUBLIC_ARTIST_IMAGE_BASE_URL, f"{artist_id}-cover",
                        )
            except Exception as exc:
                st.error(f"Image upload failed: {exc}")
                st.stop()

            data = {
                "artistId": artist_id, "name": name, "slug": slug,
                "artistStatement": artist_statement, "profileImageUrl": profile_url,
                "coverImageUrl": cover_url, "location": location,
                "mediums": [m.strip() for m in mediums.split(",") if m.strip()],
                "website": website, "instagram": instagram,
                "featured": featured, "active": active,
            }
            try:
                upsert_artist(data)
                st.success("Saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

        st.divider()
        st.subheader("Delete this artist")
        confirm = st.checkbox(
            f"I understand this will permanently delete \"{artist['name']}\".", key="confirm_delete_artist"
        )
        if st.button("Delete artist", disabled=not confirm):
            result = delete_artist(artist_id)
            if result["deleted"]:
                st.success("Deleted.")
                st.rerun()
            else:
                st.error(
                    f"Cannot delete — {result['blocked_by_artwork_count']} artwork(s) still reference this "
                    "artist. Reassign or delete them first."
                )
