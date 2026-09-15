"""
Extracts and structures EXIF/metadata from an image file.
"""
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, IFD
import pillow_heif

pillow_heif.register_heif_opener()

_XMP_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_XMP_EXIF_NS = "http://ns.adobe.com/exif/1.0/"
_XMP_DC_NS = "http://purl.org/dc/elements/1.1/"
_XMP_XAP_NS = "http://ns.adobe.com/xap/1.0/"

_TAG_IDS = {v: k for k, v in TAGS.items()}
_KEEP_GROUPS = {
    "artist": ("Artist", "Copyright"),
    "camera": ("Make", "Model"),
    "software": ("Software",),
}

def _convert_gps_coord(coord, ref):
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
            result["latitude"] = _convert_gps_coord(lat_val, lat_ref)
        if lon_val and lon_ref:
            result["longitude"] = _convert_gps_coord(lon_val, lon_ref)
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

def _xmp_find(root, ns, local):
    for el in root.iter():
        val = el.attrib.get(f"{{{ns}}}{local}")
        if val:
            return val
    el = root.find(f".//{{{ns}}}{local}")
    if el is not None:
        li = el.find(f".//{{{_XMP_RDF_NS}}}li")
        if li is not None and li.text:
            return li.text.strip()
        if el.text and el.text.strip():
            return el.text.strip()
    return None

def _parse_xmp_gps_coord(value):
    try:
        hemi = value[-1]
        deg_str, min_str = value[:-1].split(",")
        decimal = float(deg_str) + float(min_str) / 60.0
        if hemi in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None

def _decimal_to_dms(decimal):
    decimal = abs(decimal)
    degrees = int(decimal)
    minutes_full = (decimal - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return (float(degrees), float(minutes), float(seconds))

def _parse_xmp(xmp_bytes) -> dict:
    result = {}
    try:
        root = ET.fromstring(xmp_bytes)
        lat = _xmp_find(root, _XMP_EXIF_NS, "GPSLatitude")
        lon = _xmp_find(root, _XMP_EXIF_NS, "GPSLongitude")
        creator = _xmp_find(root, _XMP_DC_NS, "creator")
        tool = _xmp_find(root, _XMP_XAP_NS, "CreatorTool")
        if lat and lon:
            result["latitude"] = _parse_xmp_gps_coord(lat)
            result["longitude"] = _parse_xmp_gps_coord(lon)
        if creator:
            result["Artist"] = creator
        if tool:
            result["Software"] = tool
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

    # getexif() only returns the base IFD, Exif/GPS sub-IFDs need get_ifd()
    exif = img.getexif()
    exif_dict = {}
    gps_raw = {}
    has_thumbnail = False

    if exif is not None:
        merged = dict(exif)
        try:
            merged.update(exif.get_ifd(0x8769))
        except (KeyError, ValueError):
            pass
        try:
            gps_ifd = exif.get_ifd(0x8825)
            if gps_ifd:
                gps_raw = dict(gps_ifd)
        except (KeyError, ValueError):
            pass
        try:
            has_thumbnail = 0x0201 in exif.get_ifd(IFD.IFD1)
        except (KeyError, ValueError):
            pass

        for tag_id, value in merged.items():
            if tag_id in (0x8769, 0x8825):
                continue
            tag_name = TAGS.get(tag_id, tag_id)
            try:
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                elif hasattr(value, "numerator"):
                    value = float(value)
                elif isinstance(value, tuple):
                    value = [float(v) if hasattr(v, "numerator") else v for v in value]
                json.dumps(value)
                exif_dict[str(tag_name)] = value
            except (TypeError, ValueError):
                exif_dict[str(tag_name)] = str(value)

    xmp_raw = img.info.get("xmp")
    xmp_data = _parse_xmp(xmp_raw) if xmp_raw else {}
    for field in ("Artist", "Software"):
        if xmp_data.get(field) and field not in exif_dict:
            exif_dict[field] = xmp_data[field]

    INTERESTING = [
        "Make", "Model", "Software", "DateTime", "DateTimeOriginal",
        "DateTimeDigitized", "ExposureTime", "FNumber", "ISOSpeedRatings",
        "FocalLength", "Flash", "WhiteBalance", "ExposureMode",
        "MeteringMode", "LightSource", "SceneCaptureType", "Orientation",
        "Artist", "Copyright", "ImageDescription", "UserComment",
        "XResolution", "YResolution"
    ]
    result["exif"] = {k: exif_dict[k] for k in INTERESTING if k in exif_dict}

    if gps_raw:
        result["gps"] = _parse_gps(gps_raw)

    if "latitude" not in result["gps"] and xmp_data.get("latitude") is not None:
        result["gps"]["latitude"] = xmp_data["latitude"]
        result["gps"]["longitude"] = xmp_data["longitude"]
        result["gps"]["google_maps"] = (
            f"https://maps.google.com/?q={xmp_data['latitude']},{xmp_data['longitude']}"
        )

    risks = []
    risk_level = "Low"

    if result["gps"].get("latitude"):
        risks.append("GPS coordinates embedded, reveals exact photo location")
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

    if has_thumbnail:
        risks.append("Embedded preview thumbnail present, may carry its own copy of metadata")

    if not risks:
        risks.append("No sensitive metadata detected")

    result["privacy_risk"] = {
        "level": risk_level,
        "details": risks
    }

    return result

def strip_metadata(filepath: str, output_path: str = None, output_format: str = None, quality: int = 85, keep=None) -> dict:
    """
    Removes all EXIF/metadata from an image, optionally converting format and keeping select fields.
    """
    if not os.path.isfile(filepath):
        return {"error": f"File not found: {filepath}"}

    if output_path is None:
        name, ext = os.path.splitext(filepath)
        output_path = f"{name}_clean{ext}"

    try:
        img = Image.open(filepath)
        original_exif = img.getexif()
        xmp_raw = img.info.get("xmp")
        xmp_data = _parse_xmp(xmp_raw) if xmp_raw else {}
        if img.mode == "P":
            img = img.convert("RGB")

        fmt = output_format or img.format or "JPEG"
        if fmt == "JPEG" and img.mode in ("RGBA", "LA"):
            img = img.convert("RGB")
        if img.mode == "CMYK" and fmt not in ("JPEG", "TIFF"):
            img = img.convert("RGB")

        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        save_kwargs = {"quality": quality} if fmt == "JPEG" else {}

        if keep:
            new_exif = Image.Exif()
            if "gps" in keep:
                gps_ifd = original_exif.get_ifd(0x8825)
                if gps_ifd:
                    new_exif[0x8825] = dict(gps_ifd)
                elif xmp_data.get("latitude") is not None:
                    lat, lon = xmp_data["latitude"], xmp_data["longitude"]
                    new_exif[0x8825] = {
                        1: "N" if lat >= 0 else "S",
                        2: _decimal_to_dms(lat),
                        3: "E" if lon >= 0 else "W",
                        4: _decimal_to_dms(lon),
                    }
            for group in keep:
                for name in _KEEP_GROUPS.get(group, ()):
                    tag_id = _TAG_IDS.get(name)
                    if tag_id is None:
                        continue
                    if tag_id in original_exif:
                        new_exif[tag_id] = original_exif[tag_id]
                    elif xmp_data.get(name):
                        new_exif[tag_id] = xmp_data[name]
            if len(new_exif):
                save_kwargs["exif"] = new_exif.tobytes()

        clean.save(output_path, format=fmt, **save_kwargs)
        size_before = os.path.getsize(filepath)
        size_after  = os.path.getsize(output_path)
        return {
            "success": True,
            "output_path": output_path,
            "filename": os.path.basename(output_path),
            "format": fmt,
            "size_before_kb": round(size_before / 1024, 2),
            "size_after_kb":  round(size_after  / 1024, 2),
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract or strip EXIF/XMP metadata from images")
    parser.add_argument("paths", nargs="+", help="image file(s)")
    parser.add_argument("--strip", action="store_true", help="strip metadata instead of analyzing")
    parser.add_argument("--format", choices=["jpeg", "png", "webp", "bmp", "tiff"], help="convert format when stripping")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality 1-100 (default 85)")
    parser.add_argument("--keep", action="append", choices=["gps", "artist", "camera", "software"], help="keep this field group when stripping (repeatable)")
    parser.add_argument("--output", help="output directory for stripped files (default: alongside source)")
    parser.add_argument("--json", action="store_true", help="compact single-line JSON, for scripting")
    args = parser.parse_args()

    for path in args.paths:
        if args.strip:
            output_path = None
            if args.output:
                os.makedirs(args.output, exist_ok=True)
                name, ext = os.path.splitext(os.path.basename(path))
                output_path = os.path.join(args.output, f"{name}_clean{ext}")
            result = strip_metadata(
                path, output_path,
                output_format=args.format.upper() if args.format else None,
                quality=args.quality,
                keep=args.keep,
            )
        else:
            result = extract_metadata(path)

        print(json.dumps(result) if args.json else json.dumps(result, indent=2))