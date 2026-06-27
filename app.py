"""
Backend: Flask server that receives image uploads and returns metadata as JSON
"""

import os
import json

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from exif_reader import extract_metadata

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "webp", "heic", "bmp"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No Image field in requests"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify ({
            "error": f"File type not supported. Allowed: {'. '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    metadata = extract_metadata(save_path)

    # Clean up uploaded file after analysis
    try:
        os.remove(save_path)
    except OSError:
        pass

    return jsonify(metadata)

@app.route("/strip", methods=["POST"])
def strip():
    if "image" not in request.files:
        return jsonify({"error": "No image field in request"}), 400

    file = request.files["image"]

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400

    filename    = secure_filename(file.filename)
    save_path   = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    output_path = os.path.join(app.config["UPLOAD_FOLDER"], "clean_" + filename)
    file.save(save_path)

    from exif_reader import strip_metadata
    result = strip_metadata(save_path, output_path)

    if "error" in result:
        os.remove(save_path)
        return jsonify(result), 500

    # Send the clean file back as a download
    from flask import send_file
    response = send_file(
        output_path,
        as_attachment=True,
        download_name="clean_" + filename
    )

    # Cleanup both files after sending
    @response.call_on_close
    def cleanup():
        for p in (save_path, output_path):
            try: os.remove(p)
            except OSError: pass

    return response

@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "EXIF inspector running"})

if __name__ == "__main__":
    print("=" * 50)
    print("EXIF Inspector — running on http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)