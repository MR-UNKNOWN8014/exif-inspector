"""
Extracts and structures EXIF/metadata from an image file.
"""
import os
import json
from datetime import datetime
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS

def _convet_gps_coord(coord, ref):
    try:
        degrees = float(coord[0])
        minutes = float(coord[1])
        seconds = float(coord[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None

def _parse_gps(gps_data: dict) -> dict:
    result = {}
    try:
        lat_val = gps_data.get(2)
        lat_ref = gps_data.get(1)
        lon_val = gps_data.get(4)
        lon_ref = gps_data.get(3)
        alt_val = gps_data.get(6)
        alt_ref = gps_data.get(5)

        if lat_val and lat_ref:
            result["Latitude"] = _convet_gps_coord(lat_val, lat_ref)
        if lon_val and lon_ref:
            result["Longitude"] = _convet_gps_coord(lon_val, lon_ref)
        if alt_val is not None:
            alt_m = float(alt_val)
            if alt_ref == 1:
                alt_m = -alt_m
            result["altitude_m"] = round(alt_m, 2)
        if "latitude" in result and "longitude" in result:
            result["google_maps"] = (
                f"https://maps.google.com/?q={result['latitude']},{result['longitude']}"
            )
    except Exception:
        pass
    return result


def extract_metadata(filepath: str) -> dict:
    if not os.path.isfile(filepath):
        return {"error": f"File not found: {filepath}"}

    result = {
        "file_info": {},
        "image_info": {},
        "exif": {},
        "gps": {},
        "privacy_risk": {}
    }

    # File Level Info
    stat = os.stat(filepath)
    result["file_info"] = {
        "filename": os.path.basename(filepath),
        "filepath": os.path.abspath(filepath),
        "size_bytes": stat.st_size,
        "size_kb": round(stat.st_size / 1024, 2),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "extension": os.path.splitext(filepath)[1].upper().lstrip(".")
    }

    try:
        img = Image.open(filepath)
    except Exception as e:
        return {"error": f"Cannot open image file: {e}"}


    # Image Level Info
    width, height = img.size
    dpi = img.info.get("dpi")
    result["image_info"] = {
        "width_px": width,
        "height_px": height,
        "megapixels": round((width * height) / 1_000_000, 2),
        "mode": img.mode,
        "format": img.format or result["file_info"]["extension"],
        "dpi": f"{int(dpi[0])} x {int(dpi[1])}" if dpi else "Not specified"
    }

    # EXIF Data
    raw_exif = img._getexif() if hasattr(img, "_getexif") else None
    exif_dict = {}
    gps_raw = {}

    if raw_exif:
        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name == "GPSInfo":
                for gps_id, gps_val in value.items():
                    gps_raw[gps_id] = gps_val
                continue
            # Convert IFDRational / bytes to serializable types
            try:
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                elif hasattr(value, "numerator"):
                    value = float(value)
                elif isinstance(value, tuple):
                    value = [float(v) if hasattr(v, "numerator") else v for v in value]
                json.dumps(value)  # test serializability
                exif_dict[str(tag_name)] = value
            except (TypeError, ValueError):
                exif_dict[str(tag_name)] = str(value)

        # Curate the most useful EXIF fields for the dashboard
    INTERESTING = [
        "Make", "Model", "Software", "DateTime", "DateTimeOriginal",
        "DateTimeDigitized", "ExposureTime", "FNumber", "ISOSpeedRatings",
        "FocalLength", "Flash", "WhiteBalance", "ExposureMode",
        "MeteringMode", "LightSource", "SceneCaptureType", "Orientation",
        "Artist", "Copyright", "ImageDescription", "UserComment",
        "XResolution", "YResolution"
    ]
    result["exif"] = {k: exif_dict[k] for k in INTERESTING if k in exif_dict}


    # GPS
    if gps_raw:
        result["gps"] = _parse_gps(gps_raw)


    # Privacy Risk Assessment
    risks = []
    risk_level = "Low"

    if result["gps"].get("latitude"):
        risks.append("GPS coordinates embedded — reveals exact photo location")
        risk_level = "High"

    for field in ("Artist", "Copyright"):
        if field in result["exif"]:
            risks.append(f"'{field}' field contains: {result['exif'][field]}")
            if risk_level != "High":
                risk_level = "Medium"

    cam = result["exif"].get("Make", "") + " " + result["exif"].get("Model", "")
    if cam.strip():
        risks.append(f"Device fingerprint present: {cam.strip()}")
        if risk_level == "Low":
            risk_level = "Medium"

    if result["exif"].get("Software"):
        risks.append(f"Software tag: {result['exif']['Software']}")

    if not risks:
        risks.append("No sensitive metadata detected")

    result["privacy_risk"] = {
        "level": risk_level,
        "details": risks
    }

    return result

def strip_metadata(filepath: str, output_path: str = None) -> dict:
    """
    Removes all EXIF/metadata from an image.
    """
    if not os.path.isfile(filepath):
        return {"error": f"File not found: {filepath}"}

    if output_path is None:
        name, ext = os.path.splitext(filepath)
        output_path = f"{name}_clean{ext}"

    try:
        img = Image.open(filepath)
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        clean.save(output_path)
        size_before = os.path.getsize(filepath)
        size_after  = os.path.getsize(output_path)
        return {
            "success": True,
            "output_path": output_path,
            "filename": os.path.basename(output_path),
            "size_before_kb": round(size_before / 1024, 2),
            "size_after_kb":  round(size_after  / 1024, 2),
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python exif_reader.py <image_path>")
        sys.exit(1)
    data = extract_metadata(sys.argv[1])
    print(json.dumps(data, indent=2))