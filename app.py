import streamlit as st

from lib.auth import logout_button, require_login
from lib.db import count_artists, count_artworks, count_collections, test_connection

st.set_page_config(page_title="Aartverse Admin", page_icon="🎨", layout="wide")

require_login()
logout_button()

st.title("Aartverse Admin")
st.caption("Changes made here write directly to the live Aartverse database.")

ok, message = test_connection()
if ok:
    st.success(message)
else:
    st.error(f"Database connection failed: {message}")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Artists", count_artists())
col2.metric("Artworks", count_artworks())
col3.metric("Collections", count_collections())

st.divider()
st.markdown(
    "Use the sidebar to manage **Artists**, **Artworks**, **Collections**, "
    "or run a **Bulk Import** from a folder of JSON files + images."
)
