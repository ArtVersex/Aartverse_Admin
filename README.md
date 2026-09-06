# Aartverse Admin (Streamlit)

A password-gated Streamlit app for adding, updating, and deleting
**artists**, **artworks**, and **Week Best collections** on the live
Aartverse database — the same MariaDB/MySQL database the public site
(`AartVerse_v1`) reads from.

It also folds in the two things `Json_handling.html` did by hand: converting
an artwork photo to WEBP + uploading it to Hostinger over SFTP, and running
the KMeans colour analysis on it. Both now happen automatically whenever you
upload an image through this app, and both algorithms are ported verbatim
(unchanged) from your notebook — see `lib/hostinger.py` and
`lib/color_analysis.py`.

## First-time setup

You already have most of what this needs (your Anaconda environment shows
`paramiko`, `mysql-connector-python`, `Pillow`, `numpy`, and `scikit-learn`
already installed). From this folder:

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens in your browser at `http://localhost:8501`. You'll land on a
password screen.

### `.env`

Already created for you, with the same DB and Hostinger SFTP credentials
your notebook uses (copied straight out of `Json_handling.html`, never
retyped anywhere else). One thing you must change:

- `ADMIN_PASSWORD` — currently `change-this-password`. Set it to whatever
  you want to type to get into the app.

Everything else (`DB_*`, `SFTP_*`, the Hostinger folder/URL settings) is
already filled in. If you ever rotate the Hostinger or database password,
update it here.

## How the password gate works

Every page (`app.py` and everything in `pages/`) calls `require_login()` as
its very first line. Until the correct `ADMIN_PASSWORD` has been typed in
that browser session, the page shows only a password form and refuses to
render anything else — Streamlit shows the sidebar page list regardless of
login state, so each page checks independently rather than trusting a
single gate on the home page.

## What's covered

- **Artists** (`pages/1_🎨_Artists.py`) — list/search, add, edit, delete
  (blocked if any artwork still references the artist). Profile/cover
  images can be uploaded directly — they're converted to WEBP and pushed to
  Hostinger's `images/artists/` folder.
- **Artworks** (`pages/2_🖼️_Artworks.py`) — list/search/paginate, add, edit
  every field, delete (cascades its colour rows and any collection
  membership). Uploading an image here uploads it to Hostinger's
  `images/artworks/` folder *and* runs the KMeans colour analysis on it,
  writing both `feature_image_url` and the full `artwork_colors` breakdown
  in one step — exactly the two manual notebook steps, now automatic. You
  can still paste a URL by hand instead if you'd rather not upload.
- **Collections** (`pages/3_📚_Collections.py`) — Week Best collections:
  add/edit, and manage member artworks in an editable table (reorder by
  typing a new order number, remove with the checkbox column, add from a
  dropdown of everything not already in it). An artwork's own series field
  (`collection_name` / "part of a collection") is edited on the artwork's
  own form instead — that's a plain column on `artworks`, not a separate
  entity.
- **Bulk Import** (`pages/4_📥_Bulk_Import.py`) — point it at a local folder
  laid out the same way your exports already are:

  ```
  base_folder/
    artists/*.json
    artworks/*.json
    collections/*.json
    images/            (optional — <ArtworkID>.<ext>)
  ```

  Any subfolder can be missing. An artwork JSON missing `featureImageUrl`
  or `colorAnalysis` gets both filled in automatically from a matching file
  in `images/`, using the same upload + analysis path as the single-artwork
  form.

## Project layout

```
app.py                   Dashboard + login gate
lib/config.py             All settings, read from .env
lib/auth.py               Password check + per-page login gate
lib/db.py                 Every SQL query — artists/artworks/collections
lib/color_analysis.py     KMeans colour analyzer, ported from Json_handling.html
lib/hostinger.py          SFTP upload + WEBP conversion, ported from Json_handling.html
lib/bulk_import.py        3-folder batch importer
lib/ids.py                Slug + id-suggestion helper
pages/                    One file per admin section (Streamlit's multipage convention)
```

## Notes

- **No user accounts.** One shared password for whoever needs admin access
  — no per-person logins or audit log of who changed what.
- **New ids are suggested, not required to match any format.** `artist_id`
  / `artwork_id` are plain unique text columns, so a suggested id (e.g.
  `vincent-van-gogh-a1b2c3`) can always be overwritten with your own
  convention before saving.
- **Deleting an artist** is blocked while any artwork still points at them
  — reassign or delete those artworks first.
- If you ever get a MySQL access-denied error on a write, the `DB_USER` in
  `.env` doesn't have `INSERT`/`UPDATE`/`DELETE` privileges on the
  database — check that in your Hostinger hPanel.
