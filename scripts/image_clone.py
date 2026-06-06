#!/usr/bin/env python3
"""
Within-Image Clone Detection for Academic Fraud Detection.

Detects duplicated regions within a single image using a sliding window
perceptual-hash approach. Catches the classic fraud pattern of:
- Reused Western blot bands presented as different experiments
- Copy-pasted microscopy fields presented as biological replicates
- Reused gel lanes from one figure pasted into another
- Repeated ROI in a paper figure

DEPENDENCIES:
    pip install Pillow (recommended for speed; pure-Python fallback included)

USAGE:
    # Single image
    python image_clone.py --image figure1.png

    # Whole directory of figures
    python image_clone.py --paper-dir ./figures/

    # Adjust window size (smaller = more sensitive but slower)
    python image_clone.py --image figure1.png --window 32 --threshold 5

    # Adjust threshold (lower = stricter matching)
    python image_clone.py --image figure1.png --threshold 3
"""

import argparse
import hashlib
import os
import sys

# Force UTF-8 output on Windows
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


# Detect optional dependencies
PIL_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None


# ----- Perceptual hash of a region -----

def region_phash(img, x: int, y: int, w: int, h: int, hash_size: int = 8) -> str:
    """
    Compute a perceptual hash of a region in an image.
    Crop, resize to hash_size x hash_size, average, threshold.
    Returns hex string of length hash_size^2/4.
    """
    crop = img.crop((x, y, x + w, y + h))
    crop = crop.convert("L").resize((hash_size, hash_size))
    pixels = list(crop.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return hex(int(bits, 2))[2:].zfill(hash_size * hash_size // 4)


def hamming_distance(hash1: str, hash2: str) -> int:
    if hash1 == hash2:
        return 0
    try:
        bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
        bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
    except (ValueError, TypeError):
        return 999


# ----- Sliding window scan -----

def scan_for_clones(image_path: str, window: int = 32, stride: int = 16, threshold: int = 5):
    """
    Slide a window of size (window x window) over the image with given stride.
    For each position, compute a perceptual hash.
    Find pairs of positions whose hashes differ by <= threshold.
    """
    if not PIL_AVAILABLE:
        return {"error": "Pillow not installed. Install with: pip install Pillow"}

    try:
        img = Image.open(image_path)
    except Exception as e:
        return {"error": f"Could not open image: {e}"}

    w, h = img.size
    if w < window * 2 or h < window * 2:
        return {"error": f"Image too small ({w}x{h}) for window size {window}. Need at least {window*2}x{window*2}."}

    print(f"  Scanning {w}x{h} image with {window}x{window} window, stride {stride}...")

    positions = []
    hashes = []
    for y in range(0, h - window + 1, stride):
        for x in range(0, w - window + 1, stride):
            try:
                h_val = region_phash(img, x, y, window, window)
                positions.append((x, y))
                hashes.append(h_val)
            except Exception:
                continue

    if not positions:
        return {"error": "No valid positions scanned"}

    n = len(positions)
    print(f"  Computed {n} region hashes. Comparing pairs...")

    # Find near-duplicate regions
    clones = []
    seen = set()
    for i in range(n):
        for j in range(i + 1, n):
            # Skip if too far apart — duplicates within an image are usually local
            dx = abs(positions[i][0] - positions[j][0])
            dy = abs(positions[i][1] - positions[j][1])
            if dx < window and dy < window:
                continue  # overlapping windows
            dist = hamming_distance(hashes[i], hashes[j])
            if dist <= threshold:
                # Avoid reporting same clone multiple times
                pair_key = (min(i, j), max(i, j))
                if pair_key not in seen:
                    seen.add(pair_key)
                    clones.append({
                        "pos1": positions[i],
                        "pos2": positions[j],
                        "distance": dist,
                        "distance_pixels": (dx, dy),
                    })

    return {
        "image": image_path,
        "image_size": (w, h),
        "window": window,
        "stride": stride,
        "threshold": threshold,
        "n_regions_scanned": n,
        "n_clones_found": len(clones),
        "clones": clones,
    }


# ----- Reporting -----

def format_report(result: dict) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")

    if "error" in result:
        x = _safe_emoji("[X]", "[!]")
        return f"  {x} Error: {result['error']}"

    out = []
    out.append("=" * 70)
    out.append(f"  WITHIN-IMAGE CLONE DETECTION")
    out.append("=" * 70)
    out.append(f"\n  Image: {result['image']}")
    out.append(f"  Size: {result['image_size'][0]}x{result['image_size'][1]} pixels")
    out.append(f"  Window: {result['window']}x{result['window']}, stride {result['stride']}, threshold {result['threshold']}")
    out.append(f"  Regions scanned: {result['n_regions_scanned']}")
    out.append(f"  Near-duplicate regions found: {result['n_clones_found']}")

    if result['n_clones_found'] == 0:
        out.append(f"\n  {ok} No cloned regions detected.")
    else:
        out.append(f"\n  {crit} SUSPECTED CLONED REGIONS:\n")
        for i, c in enumerate(result['clones'][:20], 1):  # limit to first 20
            verdict = high if c['distance'] == 0 else crit
            out.append(f"  {i}. {verdict}  Region A ({c['pos1'][0]},{c['pos1'][1]}) <-> Region B ({c['pos2'][0]},{c['pos2'][1]})")
            out.append(f"     Hamming distance: {c['distance']}  |  Distance: {c['distance_pixels']} pixels")
            out.append("")
        if len(result['clones']) > 20:
            out.append(f"  ... and {len(result['clones']) - 20} more (truncated)")

    if not PIL_AVAILABLE:
        out.append(f"\n  [NOTE: install Pillow for full functionality: pip install Pillow]")

    return "\n".join(out)


# ----- Main -----

def main():
    parser = argparse.ArgumentParser(description="Within-image clone detection for paper figures")
    parser.add_argument("--image", help="Single image to scan")
    parser.add_argument("--paper-dir", help="Directory of images to scan")
    parser.add_argument("--window", type=int, default=32, help="Window size in pixels (default 32)")
    parser.add_argument("--stride", type=int, default=16, help="Sliding window stride (default 16)")
    parser.add_argument("--threshold", type=int, default=5, help="Hamming distance threshold (default 5, lower = stricter)")
    args = parser.parse_args()

    if args.image:
        result = scan_for_clones(args.image, args.window, args.stride, args.threshold)
        print(format_report(result))
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

        print(f"Scanning {len(images)} images in {args.paper_dir}...\n")
        total_clones = 0
        for img_path in images:
            print(f"--- {os.path.basename(img_path)} ---")
            result = scan_for_clones(img_path, args.window, args.stride, args.threshold)
            print(format_report(result))
            print()
            if "n_clones_found" in result:
                total_clones += result["n_clones_found"]

        print("=" * 70)
        print(f"  TOTAL CLONES DETECTED ACROSS ALL IMAGES: {total_clones}")
        print("=" * 70)
    else:
        print("Error: provide --image or --paper-dir", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
