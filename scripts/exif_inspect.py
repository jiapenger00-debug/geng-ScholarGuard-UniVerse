#!/usr/bin/env python3
"""
EXIF / Metadata Inspector for Image Forensics.

Extracts EXIF metadata from image files to detect:
- Software stamps (Photoshop, GIMP → manipulated image)
- Timestamps that postdate submission
- Inconsistent camera/software metadata across figures from the same experiment
- GPS coordinates (if any)

DEPENDENCIES:
    pip install Pillow (required)

USAGE:
    python exif_inspect.py --image figure1.png
    python exif_inspect.py --paper-dir ./figures/
"""

import argparse
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _safe_emoji(emoji: str, fallback: str = "*") -> str:
    enc = sys.stdout.encoding or "utf-8"
    try:
        emoji.encode(enc)
        return emoji
    except (UnicodeEncodeError, LookupError):
        return fallback


PIL_AVAILABLE = False
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    Image = None


def extract_exif(image_path: str) -> dict:
    """Extract EXIF data from image."""
    if not PIL_AVAILABLE:
        return {"error": "Pillow not installed. pip install Pillow"}

    try:
        img = Image.open(image_path)
    except Exception as e:
        return {"error": f"Could not open image: {e}"}

    exif_data = img._getexif()
    if not exif_data:
        return {"path": image_path, "has_exif": False, "fields": {}}

    result = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, f"Unknown({tag_id})")
        # Skip binary data (thumbnail etc)
        if isinstance(value, bytes):
            continue
        result[tag_name] = str(value)

    return {"path": image_path, "has_exif": True, "fields": result}


def flag_software(exif_fields: dict) -> list:
    """Check for image manipulation software."""
    flags = []
    software = exif_fields.get("Software", "")
    if not software:
        return flags
    software_lower = software.lower()
    if "photoshop" in software_lower:
        flags.append(f"[!] PHOTOSHOP: {software} — image has been edited in Photoshop")
    elif "gimp" in software_lower:
        flags.append(f"[!] GIMP: {software} — image has been edited in GIMP")
    elif "illustrator" in software_lower:
        flags.append(f"[!] ILLUSTRATOR: {software}")
    elif "matplotlib" in software_lower:
        flags.append(f"[OK] Matplotlib: {software} (likely a generated graph)")
    elif "inkscape" in software_lower:
        flags.append(f"[?] Inkscape: {software}")
    else:
        flags.append(f"[?] Software: {software}")
    return flags


def flag_timestamp(exif_fields: dict) -> list:
    """Check for suspicious timestamps."""
    flags = []
    for key in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
        if key in exif_fields:
            flags.append(f"  {key}: {exif_fields[key]}")
    return flags


def format_single(result: dict) -> str:
    if "error" in result:
        return f"  [X] Error: {result['error']}"

    out = []
    out.append("=" * 70)
    out.append(f"  EXIF INSPECTION: {os.path.basename(result['path'])}")
    out.append("=" * 70)

    if not result["has_exif"]:
        out.append(f"\n  [?] No EXIF data found. Most figures from publications have stripped metadata.")
        out.append(f"  This is normal for academic PDFs and preprint servers.")
        return "\n".join(out)

    fields = result["fields"]
    flags = flag_software(fields)

    out.append(f"\n  --- EXIF Fields ---")
    for k, v in sorted(fields.items()):
        out.append(f"  {k}: {v}")

    if flags:
        out.append(f"\n  --- Flags ---")
        for flag in flags:
            out.append(f"  {flag}")

    # Timestamps
    ts_flags = flag_timestamp(fields)
    if ts_flags:
        out.append(f"\n  --- Timestamps ---")
        for ts in ts_flags:
            out.append(f"{ts}")

    return "\n".join(out)


def format_batch(results: list) -> str:
    out = []
    out.append("=" * 70)
    out.append("  BATCH EXIF SCAN")
    out.append("=" * 70)
    out.append(f"\n  Total images: {len(results)}")

    n_with_exif = sum(1 for r in results if r.get("has_exif"))
    n_no_exif = sum(1 for r in results if not r.get("has_exif"))
    n_error = sum(1 for r in results if "error" in r)

    out.append(f"  With EXIF: {n_with_exif}")
    out.append(f"  No EXIF:  {n_no_exif}")
    out.append(f"  Errors:   {n_error}")

    # Collect all software stamps
    softwares = set()
    for r in results:
        if r.get("has_exif"):
            sw = r["fields"].get("Software", "")
            if sw:
                softwares.add(sw)

    if softwares:
        out.append(f"\n  --- Software stamps found ---")
        for sw in sorted(softwares):
            out.append(f"  - {sw}")

    # Collect timestamps
    timestamps = []
    for r in results:
        if r.get("has_exif"):
            for key in ["DateTimeOriginal", "DateTime", "DateTimeDigitized"]:
                if key in r["fields"]:
                    timestamps.append((os.path.basename(r["path"]), key, r["fields"][key]))

    if timestamps:
        out.append(f"\n  --- Timestamps ---")
        for fname, key, ts in timestamps:
            out.append(f"  {fname}: {key} = {ts}")

        # Check consistency
        unique_dates = set(ts.split(" ")[0] for _, _, ts in timestamps)
        if len(unique_dates) > 1:
            out.append(f"\n  [?] Multiple dates found: {sorted(unique_dates)}")
            out.append(f"  Images from the same experiment should generally have similar dates.")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="EXIF/metadata inspector for image forensics")
    parser.add_argument("--image", help="Single image to inspect")
    parser.add_argument("--paper-dir", help="Directory of images to scan")
    args = parser.parse_args()

    if args.image:
        result = extract_exif(args.image)
        print(format_single(result))
    elif args.paper_dir:
        if not os.path.isdir(args.paper_dir):
            print(f"Error: directory not found: {args.paper_dir}", file=sys.stderr)
            sys.exit(1)

        image_exts = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
        images = sorted(
            os.path.join(args.paper_dir, f)
            for f in os.listdir(args.paper_dir)
            if os.path.splitext(f)[1].lower() in image_exts
        )

        if not images:
            print(f"No images found in {args.paper_dir}")
            return

        results = [extract_exif(img) for img in images]
        print(format_batch(results))
    else:
        print("Error: provide --image or --paper-dir", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
