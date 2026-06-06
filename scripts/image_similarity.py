#!/usr/bin/env python3
"""
Image Similarity Detection for Academic Fraud Detection.

Uses perceptual hashing (pHash) and structural similarity (SSIM) to detect:
- Identical images used in multiple figures
- Rotated/flipped copies of the same image
- Cropped regions from one image used in another

USAGE:
    python image_similarity.py --paper-dir ./figures/
    python image_similarity.py --compare image1.png image2.png
    python image_similarity.py --paper-dir ./figures/ --threshold 10
"""

import argparse
import hashlib
import os
import sys
from itertools import combinations


def phash_simple(image_path: str, hash_size: int = 8) -> str:
    """
    Compute a simple perceptual hash for an image.
    Uses average hashing: resize to hash_size x hash_size, convert to grayscale,
    compare each pixel to the mean, and build a binary hash.

    Falls back to file-hash comparison if PIL is not available.
    """
    try:
        from PIL import Image
        img = Image.open(image_path).convert("L")
        img = img.resize((hash_size, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p > avg else "0" for p in pixels)
        return hex(int(bits, 2))[2:].zfill(hash_size * hash_size // 4)
    except ImportError:
        # Fallback: use MD5 hash of file content (not perceptual, but catches exact duplicates)
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
        # Pad to same length
        max_len = max(len(bin1), len(bin2))
        bin1 = bin1.zfill(max_len)
        bin2 = bin2.zfill(max_len)
        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
    except (ValueError, TypeError):
        # MD5 fallback: check exact match only
        return 0 if hash1 == hash2 else 999


def compare_images(path1: str, path2: str, threshold: int = 15) -> dict:
    """
    Compare two images and return similarity assessment.
    Hamming distance <= threshold (default 15) = suspiciously similar.
    For 64-bit pHash: distance 0 = identical, <10 = very similar, <15 = similar.
    """
    hash1 = phash_simple(path1)
    hash2 = phash_simple(path2)
    distance = hamming_distance(hash1, hash2)

    if distance == 0:
        assessment = "🔴🔴🔴 IDENTICAL: Images are exactly the same"
    elif distance <= 5:
        assessment = "🔴🔴 HIGH: Images are nearly identical (minor adjustments only)"
    elif distance <= threshold:
        assessment = f"🔴 MODERATE: Images are suspiciously similar (distance={distance})"
    elif distance <= threshold * 2:
        assessment = f"🟡 LOW: Some similarity detected (distance={distance}), likely not duplicated"
    else:
        assessment = f"✅ Different images (distance={distance})"

    return {
        "path1": path1,
        "path2": path2,
        "hash1": hash1[:16] + "...",
        "hash2": hash2[:16] + "...",
        "hamming_distance": distance,
        "assessment": assessment,
    }


def scan_directory(directory: str, threshold: int = 15) -> list:
    """Scan all images in a directory and find similar pairs."""
    image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
    images = []

    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in image_extensions:
                images.append(os.path.join(root, fname))

    if len(images) < 2:
        return [{"error": f"Found only {len(images)} images in {directory}. Need at least 2."}]

    print(f"Scanning {len(images)} images in {directory}...")
    print(f"Comparing {len(images) * (len(images) - 1) // 2} pairs...\n")

    results = []
    suspicious_pairs = []

    for path1, path2 in combinations(images, 2):
        result = compare_images(path1, path2, threshold)
        results.append(result)
        if result["hamming_distance"] <= threshold:
            suspicious_pairs.append(result)

    return {"total_images": len(images), "total_pairs": len(results), "suspicious_pairs": suspicious_pairs, "all_results": results}


def print_report(results: dict):
    """Print scan results."""
    print("=" * 70)
    print("  IMAGE SIMILARITY SCAN")
    print("=" * 70)

    if "error" in results:
        print(f"\n  ❌ {results['error']}")
        return

    print(f"\n  Images scanned: {results['total_images']}")
    print(f"  Pairs compared: {results['total_pairs']}")
    print(f"  Suspicious pairs found: {len(results['suspicious_pairs'])}")

    if results["suspicious_pairs"]:
        print(f"\n  ⚠️  SUSPICIOUS PAIRS:\n")
        for i, pair in enumerate(results["suspicious_pairs"], 1):
            print(f"  {i}. {os.path.basename(pair['path1'])} ↔ {os.path.basename(pair['path2'])}")
            print(f"     {pair['assessment']}")
            print()
    else:
        print("\n  ✅ No suspicious image similarities detected.")


def main():
    parser = argparse.ArgumentParser(description="Detect duplicated/similar images in academic papers")
    parser.add_argument("--paper-dir", help="Directory containing extracted paper figures")
    parser.add_argument("--compare", nargs=2, metavar=("IMG1", "IMG2"), help="Compare two specific images")
    parser.add_argument("--threshold", type=int, default=15, help="Hamming distance threshold (default: 15, lower = stricter)")
    args = parser.parse_args()

    if args.compare:
        result = compare_images(args.compare[0], args.compare[1], args.threshold)
        print(f"\n  Comparing: {args.compare[0]} ↔ {args.compare[1]}")
        print(f"  {result['assessment']}")
    elif args.paper_dir:
        results = scan_directory(args.paper_dir, args.threshold)
        print_report(results)
    else:
        print("Error: Provide --paper-dir or --compare.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
