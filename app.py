"""
Backend: Flask server that receives image uploads and returns metadata as JSON
"""

import os
import io
import json
import base64
import hmac
import mimetypes
import zipfile
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
from waitress import serve
from exif_reader import extract_metadata, strip_metadata

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "webp", "heic", "bmp"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024

OUTPUT_FORMATS = {
    "jpeg": ("JPEG", "jpg"),
    "png": ("PNG", "png"),
    "webp": ("WEBP", "webp"),
    "bmp": ("BMP", "bmp"),
    "tiff": ("TIFF", "tiff"),
}
FORMAT_EXTENSIONS = {pil_format: ext for pil_format, ext in OUTPUT_FORMATS.values()}
FORMAT_EXTENSIONS["HEIF"] = "heic"
KEEP_GROUPS = {"gps", "artist", "camera", "software"}

HISTORY_FILE = "history.jsonl"
HISTORY_ENABLED = os.environ.get("HISTORY_ENABLED", "1") != "0"

AUTH_USER = os.environ.get("AUTH_USER")
AUTH_PASS = os.environ.get("AUTH_PASS")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.before_request
def require_auth():
    if not AUTH_USER or not AUTH_PASS or request.path == "/health":
        return None

    auth = request.headers.get("Authorization", "")
    user, password = "", ""
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            user, _, password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            pass

    if hmac.compare_digest(user, AUTH_USER) and hmac.compare_digest(password, AUTH_PASS):
        return None

    return "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="EXIF Inspector"'}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def log_history(filename, action, risk_level=None):
    if not HISTORY_ENABLED:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filename": filename,
        "action": action,
        "risk_level": risk_level,
    }
    try:
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

def parse_strip_params(form):
    requested_format = form.get("format", "").strip().lower()
    if requested_format and requested_format not in OUTPUT_FORMATS:
        return None, None, None, f"Output format not supported. Allowed: {', '.join(OUTPUT_FORMATS)}"

    try:
        quality = max(1, min(100, int(form.get("quality", 85))))
    except ValueError:
        quality = 85

    keep = [k for k in form.getlist("keep") if k in KEEP_GROUPS]

    return requested_format, quality, keep, None

def strip_one(file, requested_format, quality, keep):
    if not allowed_file(file.filename):
        return {"error": "File type not supported"}

    filename  = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if requested_format:
        pil_format, out_ext = OUTPUT_FORMATS[requested_format]
        output_filename = f"clean_{os.path.splitext(filename)[0]}.{out_ext}"
    else:
        pil_format = None
        output_filename = "clean_" + filename

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
    file.save(save_path)

    result = strip_metadata(save_path, output_path, output_format=pil_format, quality=quality, keep=keep)

    if "error" in result:
        os.remove(save_path)
        return {"error": result["error"]}

    download_filename = output_filename
    if not requested_format:
        actual_ext = FORMAT_EXTENSIONS.get(result.get("format", "").upper())
        if actual_ext:
            download_filename = f"clean_{os.path.splitext(filename)[0]}.{actual_ext}"

    with open(output_path, "rb") as f:
        clean_bytes = f.read()
    mimetype = mimetypes.guess_type(download_filename)[0] or "application/octet-stream"

    for p in (save_path, output_path):
        try: os.remove(p)
        except OSError: pass

    log_history(download_filename, "strip")
    return {"filename": download_filename, "bytes": clean_bytes, "mimetype": mimetype}

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No Image field in requests"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify ({
            "error": f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    metadata = extract_metadata(save_path)

    try:
        os.remove(save_path)
    except OSError:
        pass

    if "error" not in metadata:
        log_history(filename, "analyze", metadata.get("privacy_risk", {}).get("level"))

    return jsonify(metadata)

@app.route("/strip", methods=["POST"])
def strip():
    if "image" not in request.files:
        return jsonify({"error": "No image field in request"}), 400

    file = request.files["image"]

    requested_format, quality, keep, error = parse_strip_params(request.form)
    if error:
        return jsonify({"error": error}), 400

    result = strip_one(file, requested_format, quality, keep)

    if "error" in result:
        status = 400 if result["error"] == "File type not supported" else 500
        return jsonify(result), status

    return send_file(
        io.BytesIO(result["bytes"]),
        mimetype=result["mimetype"],
        as_attachment=True,
        download_name=result["filename"]
    )

@app.route("/strip-batch", methods=["POST"])
def strip_batch():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"error": "No images field in request"}), 400

    requested_format, quality, keep, error = parse_strip_params(request.form)
    if error:
        return jsonify({"error": error}), 400

    errors = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for file in files:
            result = strip_one(file, requested_format, quality, keep)
            if "error" in result:
                errors.append(f"{file.filename}: {result['error']}")
                continue
            zf.writestr(result["filename"], result["bytes"])
        if errors:
            zf.writestr("_errors.txt", "\n".join(errors))
    buf.seek(0)

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="clean_images.zip"
    )

@app.route("/history")
def history():
    if not HISTORY_ENABLED or not os.path.isfile(HISTORY_FILE):
        return jsonify([])
    with open(HISTORY_FILE) as f:
        lines = f.readlines()[-50:]
    entries = [json.loads(line) for line in lines if line.strip()]
    entries.reverse()
    return jsonify(entries)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "EXIF inspector running"})

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print(f"EXIF Inspector running on http://{host}:{port}")
    print("=" * 50)
    serve(app, host=host, port=port)