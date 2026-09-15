"""
Unit tests for the extraction module. Run: pytest test_exif_reader.py
"""
import io
import os
import piexif
from PIL import Image

from exif_reader import extract_metadata, strip_metadata


def _dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round(((deg - d) * 60 - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def _make_gps_jpeg(path):
    img = Image.new("RGB", (20, 20), color=(10, 20, 30))
    exif_bytes = piexif.dump({
        "0th": {piexif.ImageIFD.Artist: b"Tester"},
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: "N",
            piexif.GPSIFD.GPSLatitude: _dms(40.689247),
            piexif.GPSIFD.GPSLongitudeRef: "W",
            piexif.GPSIFD.GPSLongitude: _dms(74.044502),
        },
    })
    img.save(path, exif=exif_bytes)


def test_gps_produces_maps_link_and_high_risk(tmp_path):
    p = tmp_path / "gps.jpg"
    _make_gps_jpeg(str(p))
    result = extract_metadata(str(p))
    assert "google_maps" in result["gps"]
    assert result["privacy_risk"]["level"] == "High"


def test_strip_removes_exif(tmp_path):
    p = tmp_path / "gps.jpg"
    _make_gps_jpeg(str(p))
    out = tmp_path / "clean.jpg"
    result = strip_metadata(str(p), str(out))
    assert result["success"]
    assert dict(Image.open(str(out)).getexif()) == {}


def test_strip_preserves_palette_colors(tmp_path):
    p = tmp_path / "pal.png"
    img = Image.new("P", (10, 10))
    img.putpalette([i for _ in range(256) for i in (10, 20, 30)])
    img.putpixel((5, 5), 0)
    img.save(str(p))
    out = tmp_path / "pal_clean.png"
    strip_metadata(str(p), str(out))
    assert Image.open(str(out)).convert("RGB").getpixel((5, 5)) == (10, 20, 30)


def test_missing_file_returns_error():
    assert "error" in extract_metadata("no_such_file.jpg")


def test_xmp_gps_used_when_no_exif_gps(tmp_path):
    xmp = (
        b'<?xpacket begin="" id="x"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:exif="http://ns.adobe.com/exif/1.0/" '
        b'exif:GPSLatitude="10,30.000000N" exif:GPSLongitude="20,15.000000E"/>'
        b'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    p = tmp_path / "xmp.jpg"
    Image.new("RGB", (20, 20), (1, 2, 3)).save(str(p), xmp=xmp)
    result = extract_metadata(str(p))
    assert result["gps"]["latitude"] == 10.5
    assert result["gps"]["longitude"] == 20.25
    assert result["privacy_risk"]["level"] == "High"


def test_xmp_stripped(tmp_path):
    xmp = b'<?xpacket begin="" id="x"?><x:xmpmeta xmlns:x="adobe:ns:meta/"/><?xpacket end="w"?>'
    p = tmp_path / "xmp.jpg"
    out = tmp_path / "xmp_clean.jpg"
    Image.new("RGB", (20, 20), (1, 2, 3)).save(str(p), xmp=xmp)
    strip_metadata(str(p), str(out))
    assert "xmp" not in Image.open(str(out)).info


def test_xmp_gps_kept_when_requested(tmp_path):
    xmp = (
        b'<?xpacket begin="" id="x"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:exif="http://ns.adobe.com/exif/1.0/" '
        b'exif:GPSLatitude="10,30.000000N" exif:GPSLongitude="20,15.000000E"/>'
        b'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    p = tmp_path / "xmp.jpg"
    out = tmp_path / "xmp_kept.jpg"
    Image.new("RGB", (20, 20), (1, 2, 3)).save(str(p), xmp=xmp)
    strip_metadata(str(p), str(out), keep=["gps"])
    result = extract_metadata(str(out))
    assert result["gps"]["latitude"] == 10.5
    assert result["gps"]["longitude"] == 20.25


def test_selective_keep_fields(tmp_path):
    p = tmp_path / "gps.jpg"
    _make_gps_jpeg(str(p))
    out = tmp_path / "kept.jpg"
    strip_metadata(str(p), str(out), keep=["gps"])
    result = extract_metadata(str(out))
    assert "google_maps" in result["gps"]
    assert result["exif"] == {}


def test_embedded_thumbnail_detected(tmp_path):
    thumb = io.BytesIO()
    Image.new("RGB", (16, 12), (5, 5, 5)).save(thumb, format="JPEG")
    exif_dict = {
        "0th": {},
        "Exif": {},
        "GPS": {},
        "1st": {piexif.ImageIFD.Compression: 6},
        "thumbnail": thumb.getvalue(),
    }
    p = tmp_path / "thumb.jpg"
    Image.new("RGB", (40, 30), (1, 2, 3)).save(str(p), exif=piexif.dump(exif_dict))
    result = extract_metadata(str(p))
    assert any("thumbnail" in d.lower() for d in result["privacy_risk"]["details"])
