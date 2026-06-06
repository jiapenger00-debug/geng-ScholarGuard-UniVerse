#!/usr/bin/env python3
"""
P-Curve Test for P-Hacking Detection.

Analyzes a paper's reported p-values to test for evidential value (are the
significant results "real" or just p-hacked?). Based on Simonsohn, Nelson &
Simmons (2014).

The p-curve is the distribution of significant p-values (p < 0.05). In a
healthy literature:
- Right-skewed (more p ~ 0.01 than p ~ 0.04) = real evidential value
- Flat or left-skewed (more p ~ 0.04 than p ~ 0.01) = p-hacking / selective reporting
- Bimodal / cliff at 0.05 = clear p-hacking

DEPENDENCIES:
    None (pure Python stdlib)

USAGE:
    python p_curve.py --pvals "0.01,0.03,0.04,0.02,0.01,0.008"  # real effect
    python p_curve.py --pvals "0.049,0.048,0.047,0.046,0.045,0.044"  # p-hacked!
    python p_curve.py --input pvalues.csv --column p
"""

import argparse
import csv
import math
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


def bin_pcurve(pvals: list) -> dict:
    """
    Bin p-values into 4 bins: (0, 0.01], (0.01, 0.02], (0.02, 0.03], (0.03, 0.04], (0.04, 0.05].
    Under the null of no p-hacking, p-values below 0.05 should be uniformly distributed.
    """
    sig = [p for p in pvals if 0 < p < 0.05]
    if not sig:
        return {"error": "No significant p-values (p < 0.05)"}

    n = len(sig)
    bin_edges = [0, 0.01, 0.02, 0.03, 0.04, 0.05]
    counts = [0] * 5
    for p in sig:
        for i in range(5):
            if bin_edges[i] < p <= bin_edges[i + 1]:
                counts[i] += 1
                break
    # Handle p=0 edge case
    counts[0] += sum(1 for p in sig if p == 0)

    return {
        "n_significant": n,
        "n_total": len(pvals),
        "counts": counts,
        "bins": [f"({bin_edges[i]:.2f}, {bin_edges[i+1]:.2f}]" for i in range(5)],
        "expected_per_bin": n / 5,
    }


def pcurve_skewness(counts: list) -> float:
    """Compute right-skewness of the p-curve. Positive = right-skewed (good). Negative = left-skewed (p-hacking)."""
    n = sum(counts)
    if n < 5:
        return 0.0
    # Weight each bin by its midpoint
    mids = [0.005, 0.015, 0.025, 0.035, 0.045]
    mean_p = sum(mids[i] * counts[i] for i in range(5)) / n
    # Compare to uniform midpoint (0.025)
    expected_midpoint = 0.025
    return expected_midpoint - mean_p  # positive = right-skewed = good


def chi2_flat_test(counts: list, expected: float) -> dict:
    """Chi-square test against uniform distribution across 5 bins."""
    chi2 = sum((c - expected) ** 2 / expected for c in counts)
    from_low_to_high = counts[0] + counts[1] + counts[2] + counts[3] + counts[4]
    # Approximate p-value (df=4)
    df = 4
    p = 1.0 - _chi2_cdf_simple(chi2, df)
    return {"chi2": round(chi2, 3), "df": df, "p_value": round(p, 4)}


def _log_gamma(x: float) -> float:
    if x <= 0:
        return float("inf")
    cof = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5]
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in cof:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def _chi2_cdf_simple(x: float, df: float) -> float:
    if x <= 0:
        return 0.0
    half_df = df / 2.0
    half_x = x / 2.0
    if half_x < half_df + 1:
        ap = half_df
        sum_val = 1.0 / half_df
        delta = sum_val
        for _ in range(200):
            ap += 1.0
            delta *= half_x / ap
            sum_val += delta
            if abs(delta) < abs(sum_val) * 1e-12:
                break
        return sum_val * math.exp(-half_x + half_df * math.log(half_x) - _log_gamma(half_df))
    else:
        b = half_x + 1.0 - half_df
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - half_df)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < 1e-12:
                break
        return 1.0 - h * math.exp(-half_x + half_df * math.log(half_x) - _log_gamma(half_df))


def format_report(result: dict) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    if "error" in result:
        return f"  [X] Error: {result['error']}"

    out = []
    out.append("=" * 70)
    out.append("  P-CURVE ANALYSIS (Simonsohn, Nelson & Simmons 2014)")
    out.append("=" * 70)
    out.append(f"\n  Total p-values: {result.get('n_total', '?')}")
    out.append(f"  Significant (p < 0.05): {result['n_significant']}")

    counts = result["counts"]
    expected = result["expected_per_bin"]
    skew = pcurve_skewness(counts)

    out.append(f"\n  --- Distribution ---")
    out.append(f"  {'Bin':<20} {'Count':<8} {'Expected':<10} {'Bar'}")
    out.append(f"  {'-'*50}")
    max_count = max(counts) if max(counts) > 0 else 1
    for i in range(5):
        bar = "#" * max(1, int(counts[i] / max_count * 20))
        flag = ""
        if expected > 0 and abs(counts[i] - expected) / expected > 0.5:
            flag = " [!]"
        out.append(f"  {result['bins'][i]:<20} {counts[i]:<8} {expected:<10.1f} {bar}{flag}")

    # Skewness assessment
    out.append(f"\n  --- Assessment ---")
    out.append(f"  P-curve skewness: {skew:+.4f} (positive = right-skewed = real evidential value)")

    if skew > 0.005:
        out.append(f"\n  {ok} RIGHT-SKEWED: The p-curve shows strong evidential value.")
        out.append(f"     Results are consistent with real effects, not p-hacking.")
    elif skew > 0.0:
        out.append(f"\n  {warn} WEAKLY RIGHT-SKEWED: Marginal evidence of real effects.")
        out.append(f"     Could be consistent with low power + some p-hacking.")
    elif skew > -0.003:
        out.append(f"\n  {warn} FLAT P-CURVE: No clear evidential value — low power or")
        out.append(f"     some p-hacking may be present. Also consistent with underpowered studies.")
    else:
        out.append(f"\n  {crit} LEFT-SKEWED: P-hacking detected! P-values cluster near 0.05.")
        out.append(f"     This pattern strongly suggests p-hacking / selective reporting.")

    # Chi-square test
    chi2_res = chi2_flat_test(counts, expected)
    out.append(f"\n  Chi-square test vs uniform: chi2={chi2_res['chi2']}, p={chi2_res['p_value']}")
    if chi2_res['p_value'] < 0.05:
        out.append(f"  {warn} P-curve is not uniform (p < 0.05)")
        # Check if there's a cliff at 0.05
        ratio_04_05 = counts[4] / expected if expected > 0 else 0
        ratio_0_01 = counts[0] / expected if expected > 0 else 0
        if ratio_04_05 > 1.5 and ratio_0_01 < 0.8:
            out.append(f"  {crit} CLIFF AT 0.05: Many p-values just below 0.05, very few low p-values")
            out.append(f"     This is the CLASSIC signature of p-hacking!")
        elif ratio_04_05 > 1.3:
            out.append(f"  {high} Cluster near 0.05 suggests p-hacking")
    else:
        out.append(f"  {ok} P-curve is fairly uniform (p >= 0.05)")

    # Count how many p-values are borderline (0.04-0.05)
    borderline = counts[4]
    borderline_pct = borderline / result["n_significant"] * 100 if result["n_significant"] > 0 else 0
    out.append(f"\n  Borderline p-values (0.04-0.05): {borderline}/{result['n_significant']} ({borderline_pct:.0f}%)")
    if borderline_pct > 30:
        out.append(f"  {high} Over 30% of significant results are borderline — suspect p-hacking")
    elif borderline_pct > 20:
        out.append(f"  {warn} 20-30% borderline — worth closer inspection")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="P-curve analysis for p-hacking detection")
    parser.add_argument("--pvals", help="Comma-separated list of p-values")
    parser.add_argument("--input", help="CSV file with p-values")
    parser.add_argument("--column", help="Column name in CSV")
    args = parser.parse_args()

    pvals = []
    if args.pvals:
        pvals = [float(x.strip()) for x in args.pvals.split(",") if x.strip()]
    elif args.input:
        if not args.column:
            print("Error: --column required with --input", file=sys.stderr)
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    pvals.append(float(row[args.column]))
                except (ValueError, KeyError):
                    continue
    else:
        for line in sys.stdin:
            try:
                pvals.append(float(line.strip()))
            except ValueError:
                continue

    if len(pvals) < 3:
        print("Error: need at least 3 p-values", file=sys.stderr)
        sys.exit(1)

    result = bin_pcurve(pvals)
    print(format_report(result))


if __name__ == "__main__":
    main()
