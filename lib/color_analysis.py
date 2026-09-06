"""
Ported verbatim (logic unchanged) from your Json_handling.html notebook's
"Colour Analayser and Updating the json" cell, so every artwork gets the
exact same color breakdown whether it goes through this app or your
original script.
"""
from __future__ import annotations

from PIL import Image
import numpy as np
from sklearn.cluster import KMeans


def get_color_name(r, g, b):
    if r < 40 and g < 40 and b < 40:
        return "Black", "Black"
    if r > 220 and g > 220 and b > 220:
        return "White", "White"
    if abs(r - g) < 15 and abs(g - b) < 15 and abs(r - b) < 15:
        if r < 80:
            return "Dark Gray", "Gray"
        elif r < 160:
            return "Gray", "Gray"
        else:
            return "Light Gray", "Gray"
    maximum = max(r, g, b)
    minimum = min(r, g, b)
    saturation = maximum - minimum
    if saturation < 35:
        if maximum < 80:
            return "Dark Gray", "Gray"
        elif maximum < 150:
            return "Gray", "Gray"
        elif maximum < 210:
            return "Light Gray", "Gray"
        else:
            return "Off White", "White"
    if r > 200 and g > 170 and b > 120:
        return "Beige", "Beige"
    if r > 150 and g > 100 and b < 100:
        return "Brown", "Brown"
    if r > 100 and g > 70 and b < 70:
        return "Dark Brown", "Brown"
    if r > g * 1.35 and r > b * 1.35:
        return ("Red", "Red") if r > 180 else ("Dark Red", "Red")
    if r > 150 and g > 70 and g < r * 0.85 and b < 100:
        return "Orange", "Orange"
    if r > 150 and g > 130 and b < 100:
        return "Yellow", "Yellow"
    if g > r * 1.15 and g > b * 1.10:
        return ("Green", "Green") if g > 150 else ("Dark Green", "Green")
    if g > r * 1.05 and b > r * 1.05 and g > 100 and b > 100:
        return "Teal", "Teal"
    if b > r * 1.25 and b > g * 1.10:
        return ("Blue", "Blue") if b > 150 else ("Dark Blue", "Blue")
    if r > g * 1.15 and b > g * 1.15:
        return "Purple", "Purple"
    if r > 150 and b > 100 and r > g * 1.25:
        return "Pink", "Pink"
    return "Other", "Other"


def rgb_to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


def analyze_image(image_path_or_file, number_of_clusters=15, top_colors=5) -> dict:
    """Accepts a path (str) or a file-like object (e.g. a Streamlit
    UploadedFile or BytesIO) — anything PIL.Image.open() accepts. Returns
    {"colorAnalysis": {"dominantColors": [...], "colorFamilies": {...}}},
    exactly the shape stored in artworks.color_analysis / artwork_colors."""
    image = Image.open(image_path_or_file).convert("RGB")
    image.thumbnail((500, 500))
    pixels = np.array(image).reshape(-1, 3)

    kmeans = KMeans(n_clusters=number_of_clusters, random_state=42, n_init=10)
    kmeans.fit(pixels)
    colors = kmeans.cluster_centers_
    labels = kmeans.labels_
    counts = np.bincount(labels)
    proportions = counts / len(labels) * 100
    sorted_indices = np.argsort(proportions)[::-1]

    dominant_colors = []
    for rank, index in enumerate(sorted_indices[:top_colors], start=1):
        r, g, b = [int(round(x)) for x in colors[index]]
        name, family = get_color_name(r, g, b)
        dominant_colors.append({
            "rank": rank, "name": name, "family": family,
            "hex": rgb_to_hex(r, g, b), "rgb": [r, g, b],
            "proportion": round(float(proportions[index]), 2),
        })

    color_families: dict[str, float] = {}
    for index in range(len(colors)):
        r, g, b = [int(round(x)) for x in colors[index]]
        _, family = get_color_name(r, g, b)
        color_families[family] = color_families.get(family, 0) + float(proportions[index])

    color_families = {
        family: round(proportion, 2)
        for family, proportion in sorted(color_families.items(), key=lambda x: x[1], reverse=True)
    }

    return {"colorAnalysis": {"dominantColors": dominant_colors, "colorFamilies": color_families}}
