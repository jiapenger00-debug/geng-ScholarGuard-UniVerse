#!/usr/bin/env python3
"""
Retraction Watch Checker for Academic Fraud Detection.

Verifies whether DOIs in a paper's reference list appear in the
Retraction Watch database (currently 20,000+ retracted papers).

Catches:
- Citing retracted work without flagging it
- Citation laundering through retracted papers
- Missing ethical acknowledgment of retractions

DEPENDENCIES:
    None (pure Python stdlib). Network: Required for first-time DB download.
    After initial download, the local CSV cache is used (fast, offline).

USAGE:
    # First time: download the Retraction Watch database
    python retraction_check.py --download

    # Then check a list of DOIs
    python retraction_check.py --input dois.txt

    # Single DOI
    python retraction_check.py --doi "10.1038/nature12373"

DATA SOURCE:
    Retraction Watch data is made available by Crossref as part of their
    retracted-publication metadata API. We use the public Crossref endpoint:
    https://api.crossref.org/works?filter=update-type:retraction

    This avoids needing a paid Retraction Watch subscription while still
    catching the bulk of retractions (Crossref indexes most major retractions).
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

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


USER_AGENT = "AcademicFraudDetector/1.0 (mailto:check@example.com)"

# Local cache file for the retracted DOIs set
DEFAULT_CACHE = os.path.expanduser("~/.cache/academic-fraud-detector/retracted_dois.json")
CROSSREF_FILTER_URL = "https://api.crossref.org/works?filter=update-type:retraction&rows={rows}&offset={offset}"
CROSSREF_DOI_URL = "https://api.crossref.org/works/{doi}"


# ----- Cache management -----

def ensure_cache_dir():
    """Make sure the cache directory exists."""
    os.makedirs(os.path.dirname(DEFAULT_CACHE), exist_ok=True)


def load_cache() -> set:
    """Load cached set of retracted DOIs."""
    if os.path.exists(DEFAULT_CACHE):
        try:
            with open(DEFAULT_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("retracted_dois", []))
        except (json.JSONDecodeError, IOError):
            return set()
    return set()


def save_cache(retracted_set: set, metadata: dict = None):
    """Save retracted DOI set to local cache."""
    ensure_cache_dir()
    payload = {
        "retracted_dois": sorted(retracted_set),
        "count": len(retracted_set),
        "metadata": metadata or {},
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(DEFAULT_CACHE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


# ----- Crossref API -----

def fetch_retracted_dois(max_results: int = 5000, delay: float = 0.2) -> set:
    """
    Fetch all retracted DOIs from Crossref. This may take several minutes
    for the full set. Uses pagination via offset.

    Returns a set of DOIs.
    """
    retracted = set()
    rows_per_page = 100
    offset = 0
    total_fetched = 0

    print(f"  Fetching retracted DOIs from Crossref (max={max_results})...")

    while total_fetched < max_results:
        url = CROSSREF_FILTER_URL.format(rows=rows_per_page, offset=offset)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status != 200:
                    print(f"  [WARN] HTTP {resp.status} at offset {offset}, stopping")
                    break
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("message", {}).get("items", [])
                if not items:
                    break
                for item in items:
                    doi = item.get("DOI")
                    if doi:
                        retracted.add(doi.lower())
                total_fetched += len(items)
                offset += rows_per_page
                if total_fetched % 500 == 0 or len(items) < rows_per_page:
                    print(f"  ...fetched {total_fetched}, unique DOIs so far: {len(retracted)}")
                if len(items) < rows_per_page:
                    break
                time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  [WARN] Network error at offset {offset}: {e}")
            break

    return retracted


def check_single_doi_retraction(doi: str) -> dict:
    """
    Check a single DOI's metadata for retraction notice.
    Returns dict with status and reason if retracted.
    """
    url = CROSSREF_DOI_URL.format(doi=urllib.parse.quote(doi, safe="/:"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return {"status": "error", "error": f"HTTP {resp.status}"}
            data = json.loads(resp.read().decode("utf-8"))
            msg = data.get("message", {})
            update_to = msg.get("update-to", [])
            for upd in update_to:
                if upd.get("type") == "retraction":
                    return {
                        "status": "retracted",
                        "reason": upd.get("reason", "(no reason given)"),
                        "by": upd.get("DOI", "?"),
                    }
            return {"status": "ok"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "not_found"}
        return {"status": "error", "error": f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"status": "error", "error": str(e)}


# ----- Reporting -----

def format_check_result(doi: str, result: dict) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    if result["status"] == "retracted":
        return (f"  {crit} RETRACTED: {doi}\n"
                f"     Reason: {result.get('reason', '?')}\n"
                f"     Retraction notice: {result.get('by', '?')}")
    elif result["status"] == "not_found":
        return f"  {warn} NOT FOUND: {doi}"
    elif result["status"] == "error":
        return f"  [E] ERROR: {doi} ({result.get('error', '?')})"
    else:
        return f"  {ok} OK: {doi}"


# ----- Main logic -----

def main():
    parser = argparse.ArgumentParser(description="Retraction Watch checker for paper references")
    parser.add_argument("--doi", help="Single DOI to check")
    parser.add_argument("--input", help="File with one DOI per line")
    parser.add_argument("--download", action="store_true", help="Download/build the retracted DOI cache")
    parser.add_argument("--max", type=int, default=5000, help="Max retractions to download (default 5000)")
    parser.add_argument("--use-cache", action="store_true", help="Use cached set (faster, less network)")
    args = parser.parse_args()

    # Mode 1: Download
    if args.download:
        print("=" * 70)
        print("  DOWNLOADING RETRACTION WATCH DATA FROM CROSSREF")
        print("=" * 70)
        print(f"\n  This may take a few minutes. Cache: {DEFAULT_CACHE}\n")
        retracted = fetch_retracted_dois(max_results=args.max)
        save_cache(retracted, {"source": "Crossref API", "method": "filter=update-type:retraction"})
        print(f"\n  [+] Done. Saved {len(retracted)} unique retracted DOIs to cache.")
        return

    # Mode 2: Single DOI live check
    if args.doi:
        print("=" * 70)
        print("  RETRACTION CHECK (LIVE)")
        print("=" * 70)
        print()
        result = check_single_doi_retraction(args.doi)
        print(format_check_result(args.doi, result))
        return

    # Mode 3: Batch check
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        dois = []
        with open(args.input, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    dois.append(line)

        if not dois:
            print("No DOIs to check.")
            return

        # Load cache if available
        cache = load_cache() if args.use_cache else set()
        cache_size = len(cache)
        if cache_size > 0:
            print(f"  Loaded {cache_size} retracted DOIs from cache.")
            print(f"  (DOIs not in cache will be checked live against Crossref.)")
        else:
            print(f"  No cache found. Run --download first for fastest batch check.")
            print(f"  (Falling back to live checks; this will be slow.)")

        print("=" * 70)
        print(f"  RETRACTION CHECK — {len(dois)} DOIs")
        print("=" * 70)
        print()

        retracted_count = 0
        for i, doi in enumerate(dois, 1):
            doi_lower = doi.lower()
            if doi_lower in cache:
                result = {"status": "retracted", "reason": "(cached)", "by": "?"}
            else:
                result = check_single_doi_retraction(doi)
                time.sleep(0.1)
            print(f"  [{i}/{len(dois)}] {format_check_result(doi, result)}")
            if result["status"] == "retracted":
                retracted_count += 1

        # Summary
        print()
        print("=" * 70)
        print("  SUMMARY")
        print("=" * 70)
        print(f"  Total DOIs checked: {len(dois)}")
        crit = _safe_emoji("[CRIT]", "[!!!]")
        print(f"  {crit} Retracted references found: {retracted_count}")
        if retracted_count > 0:
            print(f"\n  [WARN] Citing retracted work without flagging it is a significant")
            print(f"  integrity concern. Review each match manually and decide whether")
            print(f"  to retain (with explicit acknowledgment) or remove the citation.")
        return

    print("Error: provide --doi, --input, or --download", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
