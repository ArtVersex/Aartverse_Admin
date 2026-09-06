"""
Password gate shared by every page. Streamlit renders the sidebar page
list regardless of what app.py does, so a visitor could click straight
into e.g. pages/2_Artworks.py without ever seeing the login form on
app.py — that's why require_login() must be called at the very top of
EVERY page file, not just app.py.
"""
import hashlib
import hmac
import time

import streamlit as st

from lib.config import ADMIN_PASSWORD


def _safe_equal(a: str, b: str) -> bool:
    """Constant-time comparison — both inputs are hashed to a fixed-length
    digest first so a wrong guess's length or content can't be timed."""
    return hmac.compare_digest(
        hashlib.sha256(a.encode("utf-8")).digest(),
        hashlib.sha256(b.encode("utf-8")).digest(),
    )


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def require_login() -> None:
    """Call this as the first line of every page. Blocks (st.stop()) until
    the correct ADMIN_PASSWORD has been entered in this browser session."""
    if is_authenticated():
        return

    st.title("Aartverse Admin")
    st.caption("Enter the admin password to add, update, or delete artists, artworks, and collections.")

    if not ADMIN_PASSWORD:
        st.error(
            "ADMIN_PASSWORD is not set. Add it to streamlit_app/.env before "
            "anyone can log in — see .env.example."
        )
        st.stop()

    with st.form("login_form", clear_on_submit=False):
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Enter admin panel", use_container_width=True)

    if submitted:
        if password and _safe_equal(password, ADMIN_PASSWORD):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            time.sleep(0.4)  # blunt naive brute-force / timing probes
            st.error("Incorrect password.")

    st.stop()


def logout_button() -> None:
    if st.sidebar.button("Log out"):
        st.session_state["authenticated"] = False
        st.rerun()
