# EXIF Inspector

A privacy-focused tool that extracts and visualizes image metadata (EXIF data) through a local web dashboard — with an option to erase all metadata from an image and download a clean copy.

Built with Python, Flask, and Pillow. No data leaves your machine.

---

## What it does

- Extracts EXIF metadata from uploaded images: camera model, lens settings, timestamps, software tags
- Parses embedded GPS coordinates and generates a direct Google Maps link
- Runs a **privacy risk assessment** — flags device fingerprints, GPS exposure, author fields
- Lets you **erase all metadata** and download a clean version of the image
- Works entirely locally — no cloud, no third-party APIs

---

## Why this matters (security context)

Every photo taken on a smartphone or DSLR embeds metadata into the file. This includes:

- **Exact GPS coordinates** of where the photo was taken
- **Device fingerprint** (make, model, software version)
- **Timestamps** down to the second
- **Author/copyright fields** that may contain real names

Photos shared publicly on social media, forums, or emails can silently expose this data. This tool makes it visible — and gives you a one-click way to strip it before sharing.

---

## Project structure

```
exif_inspector/
├── exif_reader.py       # Core extraction and strip logic (no Flask dependency)
├── app.py               # Flask server — /analyze and /strip routes
├── dashboard.html       # Web UI — drag & drop, results, erase button
├── test_exif_reader.py  # Unit tests for the extraction module
├── requirements.txt     # Dependencies
└── .gitignore
```

---

## Setup

**Requirements:** Python 3.10+

```bash
# 1. Clone the repo
git clone https://github.com/MR-UNKNOWN8014/exif-inspector.git
cd exif-inspector

# 2. Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python app.py
```

Open your browser at `http://127.0.0.1:5000`

---

## Usage

1. Drag and drop an image onto the dashboard (or click to browse)
2. The tool extracts and displays:
    - File info (name, size, format, last modified)
    - Image info (dimensions, megapixels, color mode, DPI)
    - Camera and capture settings (make, model, ISO, aperture, shutter speed)
    - GPS location with Google Maps link (if embedded)
    - Privacy risk level: **Low / Medium / High**
3. Click **Erase metadata** to download a clean copy with all EXIF stripped

---

## Supported formats

`JPG` · `JPEG` · `PNG` · `TIFF` · `TIF` · `WEBP` · `BMP` · `HEIC`

Max file size: 20 MB

---

## Tech stack

|Layer|Technology|
|---|---|
|Backend|Python, Flask|
|Image processing|Pillow (PIL)|
|Frontend|Vanilla HTML/CSS/JS|
|Routing|Flask Blueprints|


---
