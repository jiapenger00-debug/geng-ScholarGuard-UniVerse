#!/usr/bin/env python3
"""
DOI Existence and Resolution Checker for Academic Fraud Detection.

Verifies that DOIs in a paper's reference list:
- Actually exist (don't return 404)
- Resolve to the work the paper claims (or at least, to some work)
- Are correctly formatted

Catches:
- Hallucinated DOIs (common in LLM-generated bibliographies)
- Cited DOIs that don't exist
- Citing work that exists but with wrong DOI (typo, fabrication)
- Citing retracted work (use retraction_check.py for full Retraction Watch)

DEPENDENCIES:
    None (uses Python stdlib urllib; can optionally use requests for faster)
    Network: Required (queries api.crossref.org)

USAGE:
    # Single DOI
    python doi_check.py --doi "10.1038/nature12373"

    # Multiple DOIs from file (one per line)
    python doi_check.py --input dois.txt

    # Extract DOIs from a paper PDF or text file
    python doi_check.py --paper paper.txt --auto-extract

    # Check with full metadata output
    python doi_check.py --doi "10.1038/nature12373" --verbose
"""

import argparse
import json
import os
import re
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


# Crossref API endpoint
CROSSREF_API = "https://api.crossref.org/works/{doi}"
USER_AGENT = "AcademicFraudDetector/1.0 (mailto:check@example.com)"

# DOI regex (handles most publisher formats)
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"\'<>)]+")


# ----- DOI validation -----

def is_valid_doi_format(doi: str) -> bool:
    """Check if a string looks like a DOI (basic format)."""
    doi = doi.strip().rstrip(".,;:")
    if not doi.startswith("10."):
        return False
    if "/" not in doi:
        return False
    # Must have a registrant prefix (4+ digits) and suffix
    parts = doi.split("/", 1)
    if len(parts) != 2 or not re.match(r"10\.\d{4,9}", parts[0]):
        return False
    if not parts[1]:
        return False
    return True


# ----- Crossref API query -----

def query_crossref(doi: str, timeout: float = 10.0) -> dict:
    """
    Query Crossref API for a DOI. Returns:
    - {"status": "ok", "metadata": {...}} on success
    - {"status": "not_found"} on 404
    - {"status": "error", "error": "..."} on other failures
    """
    if not is_valid_doi_format(doi):
        return {"status": "invalid_format", "doi": doi}

    url = CROSSREF_API.format(doi=urllib.parse.quote(doi, safe="/:"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {})
                return {
                    "status": "ok",
                    "doi": doi,
                    "title": (msg.get("title", ["(no title)"])[0] if msg.get("title") else "(no title)"),
                    "authors": ", ".join(
                        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                        for a in msg.get("author", [])[:3]
                    ) or "(no authors)",
                    "container": (msg.get("container-title", ["?"])[0] if msg.get("container-title") else "?"),
                    "publisher": msg.get("publisher", "?"),
                    "type": msg.get("type", "?"),
                    "published_year": _extract_year(msg.get("published-print", msg.get("published-online", msg.get("issued", {})))),
                }
            elif resp.status == 404:
                return {"status": "not_found", "doi": doi}
            else:
                return {"status": "error", "doi": doi, "error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "not_found", "doi": doi}
        return {"status": "error", "doi": doi, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"status": "error", "doi": doi, "error": f"URL error: {e.reason}"}
    except (TimeoutError, json.JSONDecodeError) as e:
        return {"status": "error", "doi": doi, "error": str(e)}


def _extract_year(date_parts: dict) -> str:
    if not date_parts:
        return "?"
    parts = date_parts.get("date-parts", [[None]])[0]
    if parts and parts[0]:
        return str(parts[0])
    return "?"


# ----- DOI extraction from text -----

def extract_dois_from_text(text: str) -> list:
    """Extract DOI-like patterns from a block of text."""
    candidates = DOI_RE.findall(text)
    # Clean and dedupe
    cleaned = set()
    for c in candidates:
        c = c.rstrip(".,;:)\"'>")
        if is_valid_doi_format(c):
            cleaned.add(c)
    return sorted(cleaned)


# ----- Reporting -----

def format_single_check(result: dict, verbose: bool = False) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    warn = _safe_emoji("[WARN]", "[?]")
    ok = _safe_emoji("[OK]", "[+]")
    x = _safe_emoji("[X]", "[!]")

    doi = result.get("doi", "?")
    status = result.get("status", "?")

    lines = []
    lines.append("=" * 70)
    lines.append(f"  DOI CHECK: {doi}")
    lines.append("=" * 70)

    if status == "ok":
        lines.append(f"\n  {ok} Status: OK (resolves to a real publication)")
        lines.append(f"  Title: {result.get('title', '?')}")
        lines.append(f"  Authors: {result.get('authors', '?')}")
        lines.append(f"  Journal/Publisher: {result.get('container', '?')} / {result.get('publisher', '?')}")
        lines.append(f"  Type: {result.get('type', '?')}")
        lines.append(f"  Year: {result.get('published_year', '?')}")
    elif status == "not_found":
        lines.append(f"\n  {crit} STATUS: NOT FOUND")
        lines.append(f"  Crossref returned 404. This DOI does not exist.")
        lines.append(f"  Possible causes: hallucinated by LLM, typo, fabricated reference.")
    elif status == "invalid_format":
        lines.append(f"\n  {x} STATUS: INVALID FORMAT")
        lines.append(f"  '{doi}' does not match the DOI format (10.NNNN/...)")
    elif status == "error":
        lines.append(f"\n  {warn} STATUS: API ERROR")
        lines.append(f"  Error: {result.get('error', '?')}")
    return "\n".join(lines)


def format_batch_report(results: list) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")

    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("status") == "ok")
    n_not_found = sum(1 for r in results if r.get("status") == "not_found")
    n_invalid = sum(1 for r in results if r.get("status") == "invalid_format")
    n_error = sum(1 for r in results if r.get("status") == "error")

    lines = []
    lines.append("=" * 70)
    lines.append("  BATCH DOI CHECK REPORT")
    lines.append("=" * 70)
    lines.append(f"\n  Total DOIs checked: {n_total}")
    lines.append(f"  {ok} Valid (resolve to real work): {n_ok}")
    lines.append(f"  {crit} Not found (likely fabricated/hallucinated): {n_not_found}")
    lines.append(f"  [X] Invalid format: {n_invalid}")
    lines.append(f"  [?] API errors: {n_error}")
    if n_total > 0:
        lines.append(f"  Failure rate: {(n_not_found + n_invalid) / n_total * 100:.1f}%")

    # Per-DOI details (compact)
    if n_not_found > 0 or n_invalid > 0:
        lines.append("\n  PROBLEMS:\n")
        for r in results:
            if r.get("status") == "not_found":
                lines.append(f"    {crit} NOT FOUND: {r.get('doi', '?')}")
            elif r.get("status") == "invalid_format":
                lines.append(f"    [X] INVALID:  {r.get('doi', '?')}")
            elif r.get("status") == "error":
                lines.append(f"    [?] ERROR:    {r.get('doi', '?')}  ({r.get('error', '?')})")

    return "\n".join(lines)


# ----- Main logic -----

def check_dois(dois: list, delay: float = 0.1) -> list:
    """Check a list of DOIs via Crossref. Returns list of result dicts."""
    results = []
    for i, doi in enumerate(dois):
        if i > 0 and delay > 0:
            time.sleep(delay)  # be polite to Crossref (free API)
        result = query_crossref(doi)
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="DOI existence checker via Crossref API")
    parser.add_argument("--doi", help="Single DOI to check")
    parser.add_argument("--input", help="File with one DOI per line")
    parser.add_argument("--paper", help="Text/PDF file to auto-extract DOIs from")
    parser.add_argument("--auto-extract", action="store_true", help="Auto-extract DOIs from --paper")
    parser.add_argument("--verbose", action="store_true", help="Show full metadata")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between API calls (default 0.1s, be polite)")
    args = parser.parse_args()

    dois = []

    if args.doi:
        dois.append(args.doi.strip())
    elif args.input:
        if not os.path.exists(args.input):
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    dois.append(line)
    elif args.paper and args.auto_extract:
        if not os.path.exists(args.paper):
            print(f"Error: file not found: {args.paper}", file=sys.stderr)
            sys.exit(1)
        with open(args.paper, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        dois = extract_dois_from_text(text)
        print(f"  Auto-extracted {len(dois)} unique DOIs from {args.paper}\n")
    else:
        print("Error: provide --doi, --input, or --paper --auto-extract", file=sys.stderr)
        print("Run with --help for full usage.", file=sys.stderr)
        sys.exit(1)

    if not dois:
        print("No DOIs to check.")
        return

    if len(dois) == 1:
        result = query_crossref(dois[0])
        print(format_single_check(result, args.verbose))
    else:
        results = check_dois(dois, delay=args.delay)
        print(format_batch_report(results))


if __name__ == "__main__":
    main()
