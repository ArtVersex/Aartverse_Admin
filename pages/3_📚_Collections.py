import pandas as pd
import streamlit as st

from lib.auth import logout_button, require_login
from lib.db import (
    add_artwork_to_collection,
    delete_collection,
    get_collection,
    get_collection_artworks,
    list_artists_for_picker,
    list_artworks_for_picker,
    list_collections,
    set_collection_artworks,
    upsert_collection,
)

st.set_page_config(page_title="Collections — Aartverse Admin", page_icon="📚", layout="wide")
require_login()
logout_button()

st.title("Collections")
st.caption(
    "Week Best editorial collections — the curated, hand-ordered sets of artworks shown on the site's "
    "/week-best pages, separate from any artist's own series (edit an artwork's own series name on its own page)."
)

NONE_ARTIST_LABEL = "— none —"

collections = list_collections()
if collections:
    st.dataframe(
        pd.DataFrame(collections)[["collection_name", "week_of", "label", "week_best_collection_id"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No collections yet.")

st.divider()
mode = st.radio("Action", ["Add new collection", "Edit / manage existing"], horizontal=True)

artists = list_artists_for_picker()
artist_options = {NONE_ARTIST_LABEL: ""}
for a in artists:
    artist_options[a["name"]] = a["artist_id"]

# ============================================================
# ADD
# ============================================================
if mode == "Add new collection":
    st.subheader("Add collection")
    with st.form("add_collection_form"):
        collection_name = st.text_input("Collection name")
        artist_choice = st.selectbox("Artist (optional)", list(artist_options.keys()))
        week_of = st.date_input("Week of", value=None)
        label = st.text_input("Label")
        headline = st.text_area("Headline")
        submitted = st.form_submit_button("Create collection", type="primary")

    if submitted:
        if not collection_name:
            st.error("Collection name is required.")
        else:
            data = {
                "collectionName": collection_name,
                "artistId": artist_options.get(artist_choice) or None,
                "weekOf": week_of.isoformat() if week_of else None,
                "label": label or None,
                "headline": headline or None,
            }
            try:
                collection_id = upsert_collection(data)
                st.success(f"Collection '{collection_name}' created (id: {collection_id}).")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

# ============================================================
# EDIT / MANAGE
# ============================================================
else:
    if not collections:
        st.info("No collections to manage yet.")
    else:
        options = {f"{c['collection_name']} ({c['week_best_collection_id']})": c["week_best_collection_id"] for c in collections}
        choice = st.selectbox("Choose a collection", list(options.keys()))
        collection_id = options[choice]
        collection = get_collection(collection_id)

        st.subheader(f"Edit {collection['collection_name']}")
        current_artist_name = NONE_ARTIST_LABEL
        for name, aid in artist_options.items():
            if aid and aid == collection.get("artist_id"):
                current_artist_name = name

        with st.form("edit_collection_form"):
            collection_name = st.text_input("Collection name", value=collection["collection_name"])
            artist_choice = st.selectbox(
                "Artist (optional)", list(artist_options.keys()), index=list(artist_options.keys()).index(current_artist_name)
            )
            week_of_value = collection.get("week_of")
            week_of = st.date_input("Week of", value=week_of_value)
            label = st.text_input("Label", value=collection.get("label") or "")
            headline = st.text_area("Headline", value=collection.get("headline") or "")
            save = st.form_submit_button("Save changes", type="primary")

        if save:
            data = {
                "collectionName": collection_name,
                "artistId": artist_options.get(artist_choice) or None,
                "weekOf": week_of.isoformat() if week_of else None,
                "label": label or None,
                "headline": headline or None,
            }
            try:
                upsert_collection(data, existing_id=collection_id)
                st.success("Saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

        st.divider()
        st.subheader("Artworks in this collection")
        members = get_collection_artworks(collection_id)

        if members:
            editor_df = pd.DataFrame(
                [{"order": m["sort_order"] + 1, "title": m["title"], "artist_name": m["artist_name"] or "",
                  "artwork_id": m["artwork_id"], "remove": False} for m in members]
            )
            edited = st.data_editor(
                editor_df,
                use_container_width=True, hide_index=True, key="collection_members_editor",
                column_config={
                    "order": st.column_config.NumberColumn("Order", min_value=1, step=1),
                    "title": st.column_config.TextColumn("Title", disabled=True),
                    "artist_name": st.column_config.TextColumn("Artist", disabled=True),
                    "artwork_id": st.column_config.TextColumn("Artwork ID", disabled=True),
                    "remove": st.column_config.CheckboxColumn("Remove"),
                },
            )
            if st.button("Save order / removals"):
                kept = edited[~edited["remove"]].sort_values("order")
                set_collection_artworks(collection_id, kept["artwork_id"].tolist())
                st.success("Updated.")
                st.rerun()
        else:
            st.caption("No artworks in this collection yet.")

        member_ids = {m["artwork_id"] for m in members}
        available = [a for a in list_artworks_for_picker() if a["artwork_id"] not in member_ids]
        if available:
            add_options = {f"{a['title']} ({a['artist_name'] or 'no artist'})": a["artwork_id"] for a in available}
            col1, col2 = st.columns([3, 1])
            with col1:
                add_choice = st.selectbox("Add artwork", list(add_options.keys()), key="add_artwork_choice")
            with col2:
                st.write("")
                st.write("")
                if st.button("Add to collection"):
                    add_artwork_to_collection(collection_id, add_options[add_choice])
                    st.rerun()

        st.divider()
        st.subheader("Delete this collection")
        st.caption("Its artworks are not deleted — only removed from this collection.")
        confirm = st.checkbox(
            f"I understand this will permanently delete \"{collection['collection_name']}\".",
            key="confirm_delete_collection",
        )
        if st.button("Delete collection", disabled=not confirm):
            delete_collection(collection_id)
            st.success("Deleted.")
            st.rerun()
