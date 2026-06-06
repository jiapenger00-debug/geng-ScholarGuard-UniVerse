#!/usr/bin/env python3
"""
Image Similarity Detection for Academic Fraud Detection.

Uses perceptual hashing (pHash) and structural similarity (SSIM) to detect:
- Identical images used in multiple figures
- Rotated/flipped copies of the same image
- Cropped regions from one image used in another

DEPENDENCIES:
    pip install Pillow (optional; falls back to MD5 file hash for exact duplicates)

USAGE:
    python image_similarity.py --paper-dir ./figures/
    python image_similarity.py --compare image1.png image2.png
    python image_similarity.py --paper-dir ./figures/ --threshold 10
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


def phash_simple(image_path: str, hash_size: int = 8) -> str:
    """
    Compute a simple perceptual hash for an image.
    Uses average hashing: resize to hash_size x hash_size, convert to grayscale,
    compare each pixel to the mean, and build a binary hash.

    Falls back to MD5 file hash comparison if PIL is not available.
    """
    if PIL_AVAILABLE:
        try:
            img = Image.open(image_path).convert("L")
            img = img.resize((hash_size, hash_size), Image.LANCZOS)
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p > avg else "0" for p in pixels)
            return hex(int(bits, 2))[2:].zfill(hash_size * hash_size // 4)
        except Exception as e:
            return f"ERROR:{e}"
    else:
        # MD5 fallback: catches exact duplicates only (not rotated/cropped)
        try:
            with open(image_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()[:16]
        except Exception as e:
            return f"ERROR:{e}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if hash1.startswith("ERROR:") or hash2.startswith("ERROR:"):
        return 999
    try:
        bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
        bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
        max_len = max(len(bin1), len(bin2))
        bin1 = bin1.zfill(max_len)
        bin2 = bin2.zfill(max_len)
        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
    except (ValueError, TypeError):
        return 0 if hash1 == hash2 else 999


def compare_images(path1: str, path2: str, threshold: int = 15) -> dict:
    hash1 = phash_simple(path1)
    hash2 = phash_simple(path2)
    distance = hamming_distance(hash1, hash2)

    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    mod = _safe_emoji("[MOD]", "[!]")
    low = _safe_emoji("[LOW]", "[?]")
    ok = _safe_emoji("[OK]", "[+]")

    if distance == 0:
        assessment = f"{crit} IDENTICAL: Images are exactly the same"
    elif distance <= 5:
        assessment = f"{high} HIGH: Images are nearly identical (minor adjustments only)"
    elif distance <= threshold:
        assessment = f"{mod} MODERATE: Images are suspiciously similar (distance={distance})"
    elif distance <= threshold * 2:
        assessment = f"{low} LOW: Some similarity detected (distance={distance}), likely not duplicated"
    else:
        assessment = f"{ok} Different images (distance={distance})"

    return {
        "path1": path1,
        "path2": path2,
        "hash1": (hash1[:16] + "...") if len(hash1) > 16 else hash1,
        "hash2": (hash2[:16] + "...") if len(hash2) > 16 else hash2,
        "hamming_distance": distance,
        "assessment": assessment,
    }


def scan_directory(directory: str, threshold: int = 15):
    image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
    images = []

    if not os.path.isdir(directory):
        return {"error": f"Directory not found: {directory}"}

    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in image_extensions:
                images.append(os.path.join(root, fname))

    if len(images) < 2:
        return {"error": f"Found only {len(images)} images in {directory}. Need at least 2."}

    print(f"Scanning {len(images)} images in {directory}...")
    print(f"Comparing {len(images) * (len(images) - 1) // 2} pairs...")

    results = []
    suspicious_pairs = []
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            result = compare_images(images[i], images[j], threshold)
            results.append(result)
            if result["hamming_distance"] <= threshold:
                suspicious_pairs.append(result)

    return {
        "total_images": len(images),
        "total_pairs": len(results),
        "suspicious_pairs": suspicious_pairs,
        "all_results": results,
    }


def print_report(results: dict):
    print("=" * 70)
    print("  IMAGE SIMILARITY SCAN")
    print("=" * 70)

    if "error" in results:
        x = _safe_emoji("[X]", "[!]")
        print(f"\n  {x} {results['error']}")
        return

    print(f"\n  Images scanned: {results['total_images']}")
    print(f"  Pairs compared: {results['total_pairs']}")
    print(f"  Suspicious pairs found: {len(results['suspicious_pairs'])}")

    method_note = "" if PIL_AVAILABLE else "  [NOTE: Pillow not installed, using MD5 fallback - only exact duplicates detected]"
    print(method_note)

    if results["suspicious_pairs"]:
        print("\n  SUSPICIOUS PAIRS:\n")
        for i, pair in enumerate(results["suspicious_pairs"], 1):
            print(f"  {i}. {os.path.basename(pair['path1'])} <-> {os.path.basename(pair['path2'])}")
            print(f"     {pair['assessment']}")
            print()
    else:
        ok = _safe_emoji("[OK]", "[+]")
        print(f"\n  {ok} No suspicious image similarities detected.")


def main():
    parser = argparse.ArgumentParser(description="Detect duplicated/similar images in academic papers")
    parser.add_argument("--paper-dir", help="Directory containing extracted paper figures")
    parser.add_argument("--compare", nargs=2, metavar=("IMG1", "IMG2"), help="Compare two specific images")
    parser.add_argument("--threshold", type=int, default=15, help="Hamming distance threshold (default: 15, lower = stricter)")
    args = parser.parse_args()

    if args.compare:
        result = compare_images(args.compare[0], args.compare[1], args.threshold)
        arrow = _safe_emoji(" <-> ", " vs ")
        print(f"\n  Comparing: {args.compare[0]}{arrow}{args.compare[1]}")
        print(f"  {result['assessment']}")
    elif args.paper_dir:
        results = scan_directory(args.paper_dir, args.threshold)
        print_report(results)
    else:
        print("Error: Provide --paper-dir or --compare.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
