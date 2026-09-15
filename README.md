# EXIF Inspector

A privacy-focused tool that extracts and visualizes image metadata through a local web dashboard, with options to erase it (fully or selectively) and convert format on download.

Built with Python, Flask, and Pillow. No data leaves your machine.

---

## What it does

- Extracts EXIF and XMP metadata: camera model, lens settings, timestamps, software tags, GPS, author
- Reads embedded GPS coordinates from either EXIF or XMP and generates a Google Maps link
- Runs a privacy risk assessment: flags GPS exposure, device fingerprints, author fields, embedded preview thumbnails
- Erases metadata, or keeps select fields (GPS, camera, author, software), and converts format on download
- Batch mode: drop multiple images, download one zip of cleaned copies
- Local scan history (opt-out) and a scriptable CLI for automation
- Print-to-PDF report view
- Optional HTTP Basic Auth for self-hosting beyond localhost
- Works entirely locally, no cloud, no third-party APIs

## Why this matters

Every photo taken on a smartphone or DSLR embeds metadata into the file: exact GPS coordinates, device make/model, timestamps down to the second, and sometimes author/copyright fields with real names. That metadata can live in EXIF or XMP, and some of it survives in an embedded preview thumbnail even after the main image is edited. Sharing that photo publicly shares all of it, silently. This tool makes it visible and gives you control over what to strip.

---

## Project structure

```
exif-inspector/
├── app.py               Flask server and routes
├── exif_reader.py        Extraction, stripping, XMP parsing, CLI
├── static/                Dashboard (HTML/CSS/JS)
├── test_exif_reader.py   pytest suite
├── Dockerfile
├── requirements.txt
```

## Setup

**Requirements:** Python 3.10+

```bash
git clone https://github.com/MR-UNKNOWN8014/exif-inspector.git
cd exif-inspector

python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows
source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

### Docker

```bash
docker build -t exif-inspector .
docker run -p 5000:5000 exif-inspector
```

Runs as a non-root user, exposes a container `HEALTHCHECK` against `/health`.

### Self-hosting (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | bind address (Docker sets `0.0.0.0`) |
| `PORT` | `5000` | port |
| `HISTORY_ENABLED` | `1` | set to `0` to disable the local scan history log entirely, including reading past entries |
| `AUTH_USER` / `AUTH_PASS` | unset | set both to require HTTP Basic Auth on every route except `/health` |

Auth is off by default, fine for `127.0.0.1`-only use. If you expose this beyond localhost, set `AUTH_USER`/`AUTH_PASS`. Basic Auth alone sends credentials in the clear, it needs a TLS-terminating reverse proxy (Caddy, nginx) in front of it for real exposure, it is not a substitute for TLS.

---

## Usage

1. Drop one or more images onto the dashboard (or click to browse). Multiple files switch to batch mode.
2. Review file info, camera/capture settings, GPS location, and privacy risk level (Low / Medium / High).
3. Optionally choose fields to keep and an output format, then click **erase metadata** to download a clean copy (a zip, in batch mode). These selections reset with every new image, nothing carries over by accident.
4. Use **print / save as PDF** for a shareable summary.
5. Open **show scan history** for a log of past analyze/strip actions (local only, opt-out via `HISTORY_ENABLED`).

### Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | dashboard |
| `/analyze` | POST | `image` file, returns metadata JSON |
| `/strip` | POST | `image` file, optional `format`/`quality`/`keep`, returns the cleaned file |
| `/strip-batch` | POST | multiple `images` files, returns a zip |
| `/history` | GET | last 50 logged actions |
| `/health` | GET | liveness check, never behind auth |

### CLI

```bash
python exif_reader.py photo.jpg                              # analyze, pretty JSON
python exif_reader.py photo.jpg --json                        # analyze, compact JSON
python exif_reader.py photo.jpg --strip --format png --output clean/
python exif_reader.py photo.jpg --strip --keep gps --keep camera
```

## Supported formats

Read: `JPG` `JPEG` `PNG` `TIFF` `TIF` `WEBP` `BMP` `HEIC`
Convert to: `JPEG` `PNG` `WEBP` `BMP` `TIFF`

Max file size: 20 MB, shared across the whole request in batch mode.

## Testing

```bash
pip install pytest piexif
python -m pytest test_exif_reader.py -q
```

`pytest` and `piexif` are test-only, not in `requirements.txt` since the app itself never imports them.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Waitress (WSGI) |
| Image processing | Pillow, pillow-heif |
| Frontend | Vanilla HTML/CSS/JS |
