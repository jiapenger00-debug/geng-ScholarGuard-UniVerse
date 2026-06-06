#!/usr/bin/env python3
"""
Text Deduplication Checker for Self-Plagiarism Detection.

Uses MinHash + LSH (Locality-Sensitive Hashing) to detect:
- Near-duplicate passages between papers (self-plagiarism)
- Recycled text blocks with minor rewording
- Salami-sliced papers (same text, different publication)

DEPENDENCIES:
    None (pure Python stdlib). Uses shingle-based Jaccard similarity.

USAGE:
    # Compare two texts
    python text_dedup.py --text1 paper1.txt --text2 paper2.txt

    # Check a single paper against a corpus
    python text_dedup.py --target paper.txt --corpus corpus_dir/

    # Self-check: find repeated passages within a single paper
    python text_dedup.py --self-check paper.txt
"""

import argparse
import hashlib
import os
import re
import sys
from collections import defaultdict

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


# ----- Shingling -----

def tokenize(text: str) -> list:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if len(w) > 1]


def shingles(words: list, k: int = 5) -> list:
    """Generate k-shingles (overlapping word n-grams)."""
    if len(words) < k:
        return []
    return [" ".join(words[i:i + k]) for i in range(len(words) - k + 1)]


def minhash_signature(shingles: list, n_hashes: int = 128) -> list:
    """MinHash signature for a set of shingles."""
    if not shingles:
        return [float("inf")] * n_hashes
    signature = [float("inf")] * n_hashes
    for shingle in shingles:
        for i in range(n_hashes):
            h = int(hashlib.md5((str(i) + shingle).encode()).hexdigest(), 16)
            if h < signature[i]:
                signature[i] = h
    return signature


def jaccard_estimate(sig1: list, sig2: list) -> float:
    """Estimate Jaccard similarity from MinHash signatures."""
    if not sig1 or not sig2:
        return 0.0
    matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matches / len(sig1)


# ----- Within-paper self-check -----

def within_paper_duplicates(text: str, window: int = 200, stride: int = 50, threshold: float = 0.6, min_spacing: int = 500) -> list:
    """
    Check for repeated passages within the same paper.
    Slides a window over the text and finds similar windows that are far apart.
    """
    words = tokenize(text)
    n = len(words)
    if n < window * 2:
        return {"error": f"Text too short ({n} words). Need at least {window*2}."}

    sigs = []
    positions = []
    for i in range(0, n - window + 1, stride):
        chunk = words[i:i + window]
        sh = shingles(chunk, k=6)
        sig = minhash_signature(sh, n_hashes=64)
        sigs.append(sig)
        positions.append(i)

    # Find similar windows that are far apart
    dupes = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            gap = abs(positions[j] - positions[i])
            if gap < min_spacing:
                continue
            sim = jaccard_estimate(sigs[i], sigs[j])
            if sim >= threshold:
                dupes.append({
                    "pos1": positions[i],
                    "pos2": positions[j],
                    "similarity": round(sim, 3),
                    "text1": " ".join(words[positions[i]:positions[i] + min(window, 20)]) + "...",
                    "text2": " ".join(words[positions[j]:positions[j] + min(window, 20)]) + "...",
                })

    return {"n_windows": len(sigs), "n_duplicates": len(dupes), "duplicates": dupes}


# ----- Cross-paper comparison -----

def compare_papers(text1: str, text2: str, threshold: float = 0.5) -> dict:
    """
    Compare two papers for overlap.
    Returns Jaccard similarity and overlapping passages.
    """
    words1 = tokenize(text1)
    words2 = tokenize(text2)

    sh1 = shingles(words1, k=6)
    sh2 = shingles(words2, k=6)

    sig1 = minhash_signature(sh1)
    sig2 = minhash_signature(sh2)

    sim = jaccard_estimate(sig1, sig2)

    # Find specific overlapping passages
    set1 = set(sh1)
    set2 = set(sh2)
    overlap = set1 & set2
    overlap_ratio = len(overlap) / max(len(set1), 1) if set1 else 0

    return {
        "jaccard_similarity": round(sim, 3),
        "shingle_overlap": len(overlap),
        "shingle_overlap_ratio": round(overlap_ratio, 3),
        "total_shingles_1": len(set1),
        "total_shingles_2": len(set2),
    }


# ----- Reporting -----

def format_within_report(result: dict) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")

    if "error" in result:
        return f"  [X] Error: {result['error']}"

    out = []
    out.append("=" * 70)
    out.append("  SELF-PLAGIARISM CHECK (Within-Paper)")
    out.append("=" * 70)
    out.append(f"\n  Windows scanned: {result['n_windows']}")
    out.append(f"  Near-duplicate passages found: {result['n_duplicates']}")

    if result["n_duplicates"] == 0:
        out.append(f"\n  {ok} No repeated passages detected.")
    else:
        out.append(f"\n  {crit} DUPLICATED PASSAGES:\n")
        for i, d in enumerate(result["duplicates"][:10], 1):
            out.append(f"  {i}. Word {d['pos1']} ↔ Word {d['pos2']} (sim={d['similarity']})")
            out.append(f"     \"{d['text1'][:120]}\"")
            out.append(f"     \"{d['text2'][:120]}\"")
            out.append("")
    return "\n".join(out)


def format_cross_report(result: dict, label1: str, label2: str) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")

    out = []
    out.append("=" * 70)
    out.append("  CROSS-PAPER DUPLICATION CHECK")
    out.append("=" * 70)
    out.append(f"\n  Paper 1: {label1} ({result['total_shingles_1']} unique shingles)")
    out.append(f"  Paper 2: {label2} ({result['total_shingles_2']} unique shingles)")
    out.append(f"\n  Jaccard similarity: {result['jaccard_similarity']}")
    out.append(f"  Shingle overlap: {result['shingle_overlap']} / {max(result['total_shingles_1'], result['total_shingles_2'])}")
    out.append(f"  Overlap ratio: {result['shingle_overlap_ratio']:.2%}")

    if result['jaccard_similarity'] > 0.3:
        out.append(f"\n  {crit} HIGH OVERLAP (>30%): Very likely self-plagiarism or duplicate publication")
    elif result['jaccard_similarity'] > 0.15:
        out.append(f"\n  {high} MODERATE OVERLAP (>15%): Significant text reuse — investigate")
    elif result['jaccard_similarity'] > 0.05:
        out.append(f"\n  [?] LOW OVERLAP (>5%): Minor text reuse, could be citations/boilerplate")
    else:
        out.append(f"\n  {ok} MINIMAL OVERLAP: Papers appear independent")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Text deduplication checker for plagiarism detection")
    parser.add_argument("--text1", help="First paper text file")
    parser.add_argument("--text2", help="Second paper text file")
    parser.add_argument("--self-check", help="Check a single paper for internal duplication")
    parser.add_argument("--target", help="Target paper to check")
    parser.add_argument("--corpus", help="Directory of papers to check against")
    args = parser.parse_args()

    if args.self_check:
        with open(args.self_check, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        result = within_paper_duplicates(text)
        print(format_within_report(result))
    elif args.text1 and args.text2:
        with open(args.text1, "r", encoding="utf-8", errors="replace") as f:
            t1 = f.read()
        with open(args.text2, "r", encoding="utf-8", errors="replace") as f:
            t2 = f.read()
        result = compare_papers(t1, t2)
        print(format_cross_report(result, os.path.basename(args.text1), os.path.basename(args.text2)))
    elif args.target and args.corpus:
        # Compare one paper against all in a directory
        with open(args.target, "r", encoding="utf-8", errors="replace") as f:
            t1 = f.read()
        img_exts = {".txt", ".md"}
        corpus_files = sorted(
            os.path.join(args.corpus, f)
            for f in os.listdir(args.corpus)
            if os.path.splitext(f)[1].lower() in img_exts
        )
        for cf in corpus_files:
            with open(cf, "r", encoding="utf-8", errors="replace") as f:
                t2 = f.read()
            result = compare_papers(t1, t2)
            jacc = result['jaccard_similarity']
            if jacc > 0.05:
                print(format_cross_report(result, os.path.basename(args.target), os.path.basename(cf)))
                print()
    else:
        print("Error: provide --text1/--text2, --self-check, or --target/--corpus", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
