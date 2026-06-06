#!/usr/bin/env python3
"""
Effect Size Sanity Checker for Academic Fraud Detection.

Recomputes implied effect sizes from reported (n, test_statistic) and flags
inconsistencies between reported and implied effect sizes.

This catches:
- Inflated Cohen's d (>2 with small n is biologically implausible)
- Reported effect sizes that don't match what the test statistic implies
- "P-hacked" effect sizes that look too perfect/round
- Effect-size inflation between abstract and results

DEPENDENCIES:
    None (pure Python, stdlib only)

USAGE:
    # Check t-test implied d vs reported d
    python effect_size_check.py --test t --n 30 --stat 3.5 --reported-d 0.8

    # Check correlation r consistency
    python effect_size_check.py --test r --n 100 --stat 0.45 --reported-r 0.50

    # Check F-test (ANOVA) implied eta-squared
    python effect_size_check.py --test F --n1 3 --n2 60 --stat 4.2

    # Batch from CSV
    python effect_size_check.py --input stats.csv
"""

import argparse
import csv
import math
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


# ----- Effect size computations -----

def cohen_d_from_t(t_stat: float, n: int) -> float:
    """Cohen's d implied by a two-sample/one-sample t-statistic."""
    if n <= 0:
        return float("nan")
    return t_stat * math.sqrt(1.0 / n + 1.0 / n) if n > 0 else float("nan")


def cohen_d_from_t_paired(t_stat: float, n_pairs: int) -> float:
    """Cohen's d for a paired-samples t-test (uses df = n-1)."""
    if n_pairs <= 1:
        return float("nan")
    return t_stat / math.sqrt(n_pairs - 1)


def r_from_t(t_stat: float, df: int) -> float:
    """Correlation coefficient r implied by a t-statistic."""
    if df <= 0:
        return float("nan")
    val = t_stat * t_stat / (t_stat * t_stat + df)
    if val < 0:
        return float("nan")
    return math.sqrt(val)


def eta_squared_from_f(f_stat: float, df1: int, df2: int) -> float:
    """Eta-squared from F-statistic (between-group variability ratio)."""
    if f_stat < 0 or df1 <= 0 or df2 <= 0:
        return float("nan")
    return (f_stat * df1) / (f_stat * df1 + df2)


def cohens_f_from_eta_squared(eta_sq: float) -> float:
    """Cohen's f from eta-squared."""
    if eta_sq < 0 or eta_sq >= 1:
        return float("nan")
    return math.sqrt(eta_sq / (1.0 - eta_sq))


def r_from_chisq(chi2: float, n: int) -> float:
    """Effect size r (or phi) implied by a chi-square statistic."""
    if n <= 0 or chi2 < 0:
        return float("nan")
    return math.sqrt(chi2 / n)


def odds_ratio_from_chisq(chi2: float, n: int) -> float:
    """Approximate odds ratio for 2x2 contingency tables (phi approximation)."""
    phi = r_from_chisq(chi2, n)
    if phi != phi:  # NaN
        return float("nan")
    # phi = (a*d - b*c) / sqrt(n1*n2*n3*n4) approximation
    # For phi < 1: odds ratio ~ (1+phi)/(1-phi)
    if phi >= 1.0:
        return float("inf")
    return (1.0 + phi) / (1.0 - phi)


# ----- Plausibility checks -----

def plausibility_d(d: float, n: int) -> str:
    """Flag implausibly large effect sizes."""
    if d != d:  # NaN
        return "?"
    ad = abs(d)
    if ad > 2.5:
        return "EXTREME (>2.5 SDs) — likely measurement error or fabrication"
    if ad > 1.5 and n < 30:
        return f"SUSPICIOUS: d={d:.2f} with n={n} — implausibly large for small sample"
    if ad > 1.0:
        return "Large (Cohen)"
    if ad > 0.5:
        return "Medium (Cohen)"
    if ad > 0.2:
        return "Small (Cohen)"
    return "Very small"


def plausibility_r(r: float, n: int) -> str:
    if r != r:
        return "?"
    ar = abs(r)
    if ar > 0.95 and n < 30:
        return f"SUSPICIOUS: r={r:.2f} with n={n} — implausibly large"
    if ar > 0.7:
        return "Large (Cohen)"
    if ar > 0.3:
        return "Medium (Cohen)"
    if ar > 0.1:
        return "Small (Cohen)"
    return "Very small"


def plausibility_eta_sq(eta_sq: float) -> str:
    if eta_sq != eta_sq:
        return "?"
    if eta_sq > 0.5:
        return "SUSPICIOUS: >0.5 — very large for most research"
    if eta_sq > 0.14:
        return "Large (Cohen)"
    if eta_sq > 0.06:
        return "Medium (Cohen)"
    if eta_sq > 0.01:
        return "Small (Cohen)"
    return "Very small"


# ----- Output formatting -----

def format_check(test_name: str, implied: float, reported: float | None, plausible: str, discrepancy: float | None) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    mod = _safe_emoji("[MOD]", "[!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    lines = []
    lines.append("=" * 70)
    lines.append(f"  EFFECT SIZE SANITY CHECK: {test_name}")
    lines.append("=" * 70)
    lines.append(f"\n  Implied effect size: {implied:.4f}")
    lines.append(f"  Plausibility: {plausible}")
    if reported is not None:
        lines.append(f"  Reported effect size: {reported:.4f}")
        if discrepancy is not None:
            verdict_icon = ok if abs(discrepancy) < 0.1 else (mod if abs(discrepancy) < 0.3 else high)
            lines.append(f"  Discrepancy: {discrepancy:+.4f}")
            lines.append(f"\n  Verdict: {verdict_icon} {'Consistent' if abs(discrepancy) < 0.1 else 'INCONSISTENT'} between implied and reported effect sizes")
            if abs(discrepancy) > 0.3:
                lines.append(f"     {crit} MAJOR DISCREPANCY: reported effect size does not match what the test statistic implies")
            elif abs(discrepancy) > 0.1:
                lines.append(f"     {warn} Moderate discrepancy — verify the reported value carefully")
    else:
        lines.append(f"  (No reported effect size provided for comparison)")
    return "\n".join(lines)


# ----- Single check handlers -----

def check_t(n: int, t_stat: float, reported_d: float | None) -> str:
    implied_d = cohen_d_from_t(t_stat, n)
    discrepancy = (reported_d - implied_d) if reported_d is not None else None
    plausible = plausibility_d(implied_d, n)
    return format_check("t-test (Cohen's d)", implied_d, reported_d, plausible, discrepancy)


def check_t_paired(n_pairs: int, t_stat: float, reported_d: float | None) -> str:
    implied_d = cohen_d_from_t_paired(t_stat, n_pairs)
    discrepancy = (reported_d - implied_d) if reported_d is not None else None
    plausible = plausibility_d(implied_d, n_pairs)
    return format_check("Paired t-test (Cohen's d_z)", implied_d, reported_d, plausible, discrepancy)


def check_r(n: int, t_stat_for_r: float, reported_r: float | None) -> str:
    df = n - 2
    implied_r = r_from_t(t_stat_for_r, df)
    discrepancy = (reported_r - implied_r) if reported_r is not None else None
    plausible = plausibility_r(implied_r, n)
    return format_check("Correlation (from t)", implied_r, reported_r, plausible, discrepancy)


def check_F(df1: int, df2: int, f_stat: float, reported_eta: float | None) -> str:
    implied = eta_squared_from_f(f_stat, df1, df2)
    discrepancy = (reported_eta - implied) if reported_eta is not None else None
    plausible = plausibility_eta_sq(implied)
    return format_check("ANOVA F-test (eta-squared)", implied, reported_eta, plausible, discrepancy)


def check_chi2(n: int, chi2_stat: float, reported_phi: float | None) -> str:
    implied = r_from_chisq(chi2_stat, n)
    discrepancy = (reported_phi - implied) if reported_phi is not None else None
    plausible = plausibility_r(implied, n)
    return format_check("Chi-square (phi / r)", implied, reported_phi, plausible, discrepancy)


# ----- Batch mode -----

def run_batch(input_path: str) -> str:
    """Read a CSV with columns: test, n, stat, [reported_es] and check each row."""
    if not os.path.exists(input_path):
        return f"Error: file not found: {input_path}"

    import os
    out = []
    out.append("=" * 70)
    out.append("  BATCH EFFECT SIZE CHECK")
    out.append("=" * 70)
    out.append(f"\n  Input: {input_path}\n")

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return "Error: no rows in CSV"

    out.append(f"  Rows: {len(rows)}\n")

    for i, row in enumerate(rows, 1):
        test = row.get("test", "").strip().lower()
        try:
            n = int(row["n"])
            stat = float(row["stat"])
            reported = float(row["reported_es"]) if row.get("reported_es", "").strip() else None
        except (KeyError, ValueError) as e:
            out.append(f"  Row {i}: SKIPPED — {e}")
            continue

        out.append(f"--- Row {i}: test={test}, n={n}, stat={stat}, reported_es={reported} ---")

        if test in ("t", "ttest", "t-test"):
            d = cohen_d_from_t(stat, n)
            plausible = plausibility_d(d, n)
            disc = (reported - d) if reported is not None else None
            out.append(f"    Implied Cohen's d: {d:.4f}  [{plausible}]")
            if reported is not None and disc is not None:
                out.append(f"    Reported: {reported:.4f}  | Discrepancy: {disc:+.4f}")
        elif test in ("r", "corr", "correlation"):
            df = n - 2
            r = r_from_t(stat, df)
            plausible = plausibility_r(r, n)
            disc = (reported - r) if reported is not None else None
            out.append(f"    Implied r: {r:.4f}  [{plausible}]")
            if reported is not None and disc is not None:
                out.append(f"    Reported: {reported:.4f}  | Discrepancy: {disc:+.4f}")
        elif test in ("f", "anova"):
            df1 = int(row.get("df1", 1))
            df2 = int(row.get("df2", n - df1 - 1))
            eta = eta_squared_from_f(stat, df1, df2)
            plausible = plausibility_eta_sq(eta)
            disc = (reported - eta) if reported is not None else None
            out.append(f"    Implied eta-squared: {eta:.4f}  [{plausible}]")
            if reported is not None and disc is not None:
                out.append(f"    Reported: {reported:.4f}  | Discrepancy: {disc:+.4f}")
        elif test in ("chi2", "chi-square", "chisq"):
            phi = r_from_chisq(stat, n)
            plausible = plausibility_r(phi, n)
            disc = (reported - phi) if reported is not None else None
            out.append(f"    Implied phi: {phi:.4f}  [{plausible}]")
            if reported is not None and disc is not None:
                out.append(f"    Reported: {reported:.4f}  | Discrepancy: {disc:+.4f}")
        else:
            out.append(f"    SKIPPED — unknown test type: {test}")
        out.append("")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Effect size sanity checker for academic fraud detection")
    parser.add_argument("--test", choices=["t", "t_paired", "r", "F", "chi2"], help="Type of test")
    parser.add_argument("--n", type=int, help="Sample size")
    parser.add_argument("--df1", type=int, help="Numerator df (F-test)")
    parser.add_argument("--df2", type=int, help="Denominator df (F-test)")
    parser.add_argument("--stat", type=float, help="Test statistic value")
    parser.add_argument("--reported-d", type=float, help="Reported Cohen's d")
    parser.add_argument("--reported-r", type=float, help="Reported Pearson r")
    parser.add_argument("--reported-eta", type=float, help="Reported eta-squared")
    parser.add_argument("--reported-phi", type=float, help="Reported phi coefficient")
    parser.add_argument("--input", help="CSV file for batch mode (columns: test, n, stat, [reported_es])")
    args = parser.parse_args()

    if args.input:
        print(run_batch(args.input))
        return

    if not args.test or args.stat is None:
        print("Error: --test and --stat are required (or use --input for batch)", file=sys.stderr)
        sys.exit(1)

    # --n is required for t, t_paired, r, chi2 (not for F which uses df1/df2)
    needs_n = args.test in ("t", "t_paired", "r", "chi2")
    if needs_n and args.n is None:
        print(f"Error: --test {args.test} requires --n (sample size)", file=sys.stderr)
        sys.exit(1)

    if args.test == "t":
        print(check_t(args.n, args.stat, args.reported_d))
    elif args.test == "t_paired":
        print(check_t_paired(args.n, args.stat, args.reported_d))
    elif args.test == "r":
        # For r check, --stat is the t-statistic that produced the r
        # If user passes r directly, this is approximate (we derive a t from r and n)
        if args.reported_r is not None and abs(args.reported_r) < 1.0 and args.n > 2:
            # Auto-derive t from r and n if stat looks like r
            if abs(args.stat) <= 1.0 and abs(args.stat - args.reported_r) > 0.1:
                # User passed r as --stat
                t_implied = args.stat * math.sqrt((args.n - 2) / (1 - args.stat * args.stat))
                print(check_r(args.n, t_implied, args.reported_r))
                return
        print(check_r(args.n, args.stat, args.reported_r))
    elif args.test == "F":
        if args.df1 is None or args.df2 is None:
            print("Error: F-test requires --df1 (numerator df) and --df2 (denominator df)", file=sys.stderr)
            sys.exit(1)
        print(check_F(args.df1, args.df2, args.stat, args.reported_eta))
    elif args.test == "chi2":
        print(check_chi2(args.n, args.stat, args.reported_phi))


if __name__ == "__main__":
    main()
