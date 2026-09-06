from __future__ import annotations

import streamlit as st

from lib.auth import logout_button, require_login
from lib.bulk_import import run_import, scan_folder

st.set_page_config(page_title="Bulk Import — Aartverse Admin", page_icon="📥", layout="wide")
require_login()
logout_button()

st.title("Bulk Import")
st.markdown(
    "Point this at a folder laid out like your existing exports:\n\n"
    "```\n"
    "base_folder/\n"
    "  artists/*.json\n"
    "  artworks/*.json\n"
    "  collections/*.json\n"
    "  images/          (optional — <ArtworkID>.<ext>)\n"
    "```\n\n"
    "Any subfolder can be missing. An artwork JSON missing `featureImageUrl` "
    "or `colorAnalysis` gets both filled in automatically from a matching "
    "file in `images/` — uploaded to Hostinger and colour-analyzed the same "
    "way the single-artwork form does."
)

base_dir = st.text_input(
    "Folder path (on this computer)",
    placeholder=r"C:\Users\Naveen\Downloads\Artverse_Product_JSON_img",
)

if base_dir:
    plan = scan_folder(base_dir)
    if plan.errors:
        for err in plan.errors:
            st.error(err)
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Artists found", len(plan.artist_files))
        col2.metric("Artworks found", len(plan.artwork_files))
        col3.metric("Collections found", len(plan.collection_files))
        st.caption(
            f"Images folder: {plan.images_dir if plan.images_dir else 'not found — image auto-fill will be skipped'}"
        )

        with st.expander("Preview files"):
            st.write("**Artists:**", [p.name for p in plan.artist_files])
            st.write("**Artworks:**", [p.name for p in plan.artwork_files])
            st.write("**Collections:**", [p.name for p in plan.collection_files])

        st.warning("This writes directly to the live database. Review the counts above before running it.")
        confirm = st.checkbox("I've reviewed this and want to import it into the live database.")

        if st.button("Run import", disabled=not confirm, type="primary"):
            log_lines: list[str] = []
            log_area = st.empty()

            def log(line: str) -> None:
                log_lines.append(line)
                log_area.code("\n".join(log_lines[-25:]))

            with st.spinner("Importing…"):
                summary = run_import(plan, log)

            st.success("Import finished.")
            st.json(summary)
            with st.expander("Full log"):
                st.code("\n".join(log_lines))
