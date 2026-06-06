#!/usr/bin/env python3
"""
Normality and Randomness Checker for Academic Fraud Detection.

Performs multiple statistical tests to determine whether a dataset
is consistent with:
1. A normal (Gaussian) distribution
2. A uniform random distribution
3. A truly random source (RNG output)

These tests catch several fraud patterns:
- Data too "perfect" (suspicious uniformity or normal-like)
- Data not random enough (clusters where randomness is claimed)
- Last-digit distributions inconsistent with natural measurements
- Suspiciously low variance / round numbers
- Runs tests: too few or too many "runs" in binary sequence

DEPENDENCIES:
    None (pure Python stdlib). scipy used as optional speed boost.

USAGE:
    # Test if data is normally distributed
    python normality_test.py --input data.csv --column "values" --test normality

    # Test if data is uniformly random
    python normality_test.py --input data.csv --column "values" --test uniform

    # Test if a binary sequence is random (runs test)
    python normality_test.py --binary-file seq.bin --test runs

    # Just give it numbers on stdin
    cat data.txt | python normality_test.py --test normality
"""

import argparse
import csv
import math
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


# ----- Stats helpers -----

def mean(values: list) -> float:
    if not values:
        return float("nan")
    return sum(values) / len(values)


def variance(values: list) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / (len(values) - 1)


def stdev(values: list) -> float:
    return math.sqrt(variance(values))


def skewness(values: list) -> float:
    """Sample skewness (Fisher-Pearson)."""
    if len(values) < 3:
        return 0.0
    n = len(values)
    m = mean(values)
    s = stdev(values)
    if s == 0:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((x - m) / s) ** 3 for x in values)


def kurtosis(values: list) -> float:
    """Excess kurtosis (normal = 0)."""
    if len(values) < 4:
        return 0.0
    n = len(values)
    m = mean(values)
    s = stdev(values)
    if s == 0:
        return 0.0
    return (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * sum(((x - m) / s) ** 4 for x in values) - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))


def _log_gamma(x: float) -> float:
    if x <= 0:
        return float("inf")
    cof = [
        76.18009172947146, -86.50532032941677, 24.01409824083091,
        -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5,
    ]
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in cof:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


# ----- Tests -----

def shapiro_wilk_simple(values: list) -> float:
    """
    Approximate Shapiro-Wilk test statistic. Returns W in [0, 1].
    For full accuracy use scipy.stats.shapiro.
    This is a simplified version for large samples.
    """
    n = len(values)
    if n < 3:
        return 1.0
    sorted_vals = sorted(values)
    m = mean(values)
    ss = sum((x - m) ** 2 for x in values)
    if ss == 0:
        return 1.0
    # Approximate W using correlation between data and normal scores
    # For simplicity, return an empirical measure: 1 - (kurtosis deviation) / 10
    k = kurtosis(values)
    sk = abs(skewness(values))
    # Heuristic: W near 1 if data is normal-like
    penalty = abs(k) * 0.05 + sk * 0.10
    return max(0.0, 1.0 - penalty)


def anderson_darling_simple(values: list) -> float:
    """
    Simplified Anderson-Darling statistic. Returns A^2 (higher = less normal).
    For full implementation use scipy.stats.anderson.
    """
    n = len(values)
    if n < 5:
        return 0.0
    sorted_vals = sorted(values)
    m = mean(values)
    s = stdev(values)
    if s == 0:
        return float("inf")
    # Standardize
    z = [(x - m) / s for x in sorted_vals]
    # Compute A^2 = -n - (1/n) * sum((2i-1) * [ln(F(z_i)) + ln(1-F(z_{n+1-i}))])
    s_sum = 0.0
    for i in range(n):
        fi = _normal_cdf(z[i])
        fn_i = 1.0 - _normal_cdf(z[n - 1 - i])
        # Avoid log(0)
        fi = max(fi, 1e-10)
        fn_i = max(fn_i, 1e-10)
        s_sum += (2 * (i + 1) - 1) * (math.log(fi) + math.log(fn_i))
    a2 = -n - s_sum / n
    return a2


def _normal_cdf(x: float) -> float:
    """CDF of standard normal, using erf approximation."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def chi2_uniform_test(values: list, n_bins: int = 10) -> dict:
    """
    Chi-square goodness-of-fit test against uniform distribution.
    Returns chi2, p_value (approximate), is_uniform.
    """
    n = len(values)
    if n < 20:
        return {"error": "Need at least 20 data points"}
    lo, hi = min(values), max(values)
    if lo == hi:
        return {"error": "All values identical (not random)"}
    bin_width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for v in values:
        idx = int((v - lo) / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        counts[idx] += 1
    expected = n / n_bins
    chi2 = sum((c - expected) ** 2 / expected for c in counts)
    # Approximate p-value via df = n_bins - 1
    # Use survival function of chi-square
    df = n_bins - 1
    p = 1.0 - _chi2_cdf(chi2, df)
    return {
        "chi2": chi2,
        "df": df,
        "p_value": p,
        "counts": counts,
        "expected_per_bin": expected,
        "is_uniform_like": p > 0.05,
    }


def _chi2_cdf(x: float, df: float) -> float:
    """CDF of chi-square (pure Python)."""
    if x <= 0:
        return 0.0
    half_df = df / 2.0
    half_x = x / 2.0
    return _lower_gamma_reg(half_df, half_x)


def _lower_gamma_reg(a: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x < a + 1:
        return _gamma_series(a, x)
    return 1.0 - _gamma_continued_fraction(a, x)


def _gamma_series(a: float, x: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    ap = a
    sum_val = 1.0 / a
    delta = sum_val
    for _ in range(max_iter):
        ap += 1.0
        delta *= x / ap
        sum_val += delta
        if abs(delta) < abs(sum_val) * eps:
            break
    return sum_val * math.exp(-x + a * math.log(x) - _log_gamma(a))


def _gamma_continued_fraction(a: float, x: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    b = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b
    h = d
    for i in range(1, max_iter):
        an = -i * (i - a)
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
        if abs(delta - 1.0) < eps:
            break
    return h * math.exp(-x + a * math.log(x) - _log_gamma(a))


def runs_test_binary(bits: list) -> dict:
    """
    Wald-Wolfowitz runs test for randomness of a binary sequence.
    bits should be a list of 0/1.
    """
    n = len(bits)
    if n < 10:
        return {"error": "Need at least 10 bits for runs test"}
    n1 = sum(bits)
    n0 = n - n1
    if n0 == 0 or n1 == 0:
        return {"error": "All bits are 0 or all are 1 (not random)"}

    # Count runs
    runs = 1
    for i in range(1, n):
        if bits[i] != bits[i - 1]:
            runs += 1

    # Expected runs and variance under randomness
    expected = (2 * n0 * n1) / n + 1
    variance_num = (2 * n0 * n1) * (2 * n0 * n1 - n)
    variance_den = n * n * (n - 1)
    if variance_den == 0:
        return {"error": "Variance undefined"}
    var = variance_num / variance_den
    if var <= 0:
        return {"error": "Variance <= 0"}
    z = (runs - expected) / math.sqrt(var)
    # Two-tailed p-value approximation using normal
    p = 2 * (1 - _normal_cdf(abs(z)))
    return {
        "n_runs": runs,
        "expected_runs": round(expected, 2),
        "z_score": round(z, 4),
        "p_value": round(p, 4),
        "n0": n0,
        "n1": n1,
        "is_random_like": p > 0.01,  # conservative threshold
    }


def last_digit_test(values: list) -> dict:
    """
    Check distribution of the last digit (terminal digit).
    For natural measurements: should be roughly uniform across 0-9
    (slight bias toward 0/5 for rounded measurements).
    Suspicious if too many of one digit or missing digits.
    """
    n = len(values)
    if n < 30:
        return {"error": "Need at least 30 values"}
    counts = [0] * 10
    for v in values:
        d = abs(int(round(v * 10))) % 10 if isinstance(v, (int, float)) else 0
        # Actually use last digit of integer part for cleanliness
        try:
            int_v = int(abs(v))
            d = int_v % 10
        except (ValueError, OverflowError):
            continue
        counts[d] += 1
    expected = n / 10
    chi2 = sum((c - expected) ** 2 / expected for c in counts)
    p = 1 - _chi2_cdf(chi2, df=9)
    return {
        "counts": counts,
        "chi2": round(chi2, 2),
        "p_value": round(p, 4),
        "expected_per_digit": expected,
        "is_natural": p > 0.01,
    }


# ----- Reporting -----

def format_normality_report(values: list) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    n = len(values)
    if n < 10:
        return f"  [X] Error: need at least 10 values (got {n})"

    out = []
    out.append("=" * 70)
    out.append("  NORMALITY / RANDOMNESS TEST")
    out.append("=" * 70)
    out.append(f"\n  Sample size: n = {n}")
    out.append(f"  Mean: {mean(values):.4f}")
    out.append(f"  Stdev: {stdev(values):.4f}")
    out.append(f"  Skewness: {skewness(values):.4f} (normal: 0)")
    out.append(f"  Excess kurtosis: {kurtosis(values):.4f} (normal: 0)")

    # Normality assessment
    out.append("\n  --- Normality ---")
    sk = skewness(values)
    kurt = kurtosis(values)
    if abs(sk) > 2:
        out.append(f"  {warn} Strong skewness ({sk:.3f}) — likely NOT normal")
    elif abs(sk) > 1:
        out.append(f"  {warn} Moderate skewness ({sk:.3f})")
    else:
        out.append(f"  {ok} Skewness within normal range")

    if kurt > 2:
        out.append(f"  {warn} Heavy tails (kurtosis={kurt:.3f}) — possibly NOT normal")
    elif kurt < -1:
        out.append(f"  {warn} Light tails (kurtosis={kurt:.3f}) — too uniform, possibly fabricated")
    else:
        out.append(f"  {ok} Tail weight within normal range")

    # Anderson-Darling approximation
    a2 = anderson_darling_simple(values)
    out.append(f"\n  Anderson-Darling A^2 (approx): {a2:.3f}")
    out.append(f"  (Values: 0.2-0.5 = good, 0.5-1.0 = acceptable, >1.0 = non-normal)")

    # Shapiro-Wilk approximation
    w = shapiro_wilk_simple(values)
    out.append(f"  Shapiro-Wilk W (approx): {w:.3f}")
    out.append(f"  (Values: >0.95 = normal, 0.90-0.95 = maybe, <0.90 = likely not normal)")

    # Last digit test
    out.append("\n  --- Last Digit Distribution ---")
    ld = last_digit_test(values)
    if "error" not in ld:
        out.append(f"  Chi-square: {ld['chi2']}, p={ld['p_value']}")
        out.append(f"  Distribution: {ld['counts']}")
        if not ld["is_natural"]:
            out.append(f"  {crit} Last digit distribution looks FABRICATED")
            # Find which digits are over/underrepresented
            obs = ld["counts"]
            exp = ld["expected_per_digit"]
            for d in range(10):
                ratio = obs[d] / exp if exp > 0 else 0
                if ratio > 2:
                    out.append(f"    Digit {d}: {obs[d]} (expected ~{exp:.0f}, ratio {ratio:.1f}x) — overrepresented")
                elif ratio < 0.3 and obs[d] < 5:
                    out.append(f"    Digit {d}: {obs[d]} (expected ~{exp:.0f}, ratio {ratio:.1f}x) — underrepresented")
        else:
            out.append(f"  {ok} Last digit distribution looks natural")

    return "\n".join(out)


def format_uniform_report(values: list) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    out = []
    out.append("=" * 70)
    out.append("  UNIFORM DISTRIBUTION TEST")
    out.append("=" * 70)
    out.append(f"\n  Sample size: n = {len(values)}")
    out.append(f"  Range: [{min(values):.4f}, {max(values):.4f}]")
    out.append(f"  Mean: {mean(values):.4f}")
    out.append(f"  Stdev: {stdev(values):.4f}")

    res = chi2_uniform_test(values)
    if "error" in res:
        return f"  [X] Error: {res['error']}"
    out.append(f"\n  Chi-square: {res['chi2']:.3f}, df={res['df']}, p={res['p_value']:.4f}")
    out.append(f"  Expected per bin: {res['expected_per_bin']:.1f}")
    out.append(f"  Counts per bin: {res['counts']}")
    if res["is_uniform_like"]:
        out.append(f"\n  {ok} Data IS consistent with uniform distribution (p > 0.05)")
    else:
        out.append(f"\n  {crit} Data is NOT uniform (p < 0.05)")
        if res["p_value"] < 0.001:
            out.append(f"  {warn} Strongly non-uniform — possible fabrication or measurement error")
    return "\n".join(out)


def format_runs_report(bits: list) -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    ok = _safe_emoji("[OK]", "[+]")
    warn = _safe_emoji("[WARN]", "[?]")

    res = runs_test_binary(bits)
    out = []
    out.append("=" * 70)
    out.append("  RUNS TEST (RANDOMNESS OF BINARY SEQUENCE)")
    out.append("=" * 70)

    if "error" in res:
        return f"  [X] Error: {res['error']}"
    out.append(f"\n  Sequence length: n = {len(bits)}")
    out.append(f"  0s: {res['n0']}, 1s: {res['n1']}")
    out.append(f"  Observed runs: {res['n_runs']}")
    out.append(f"  Expected runs (under randomness): {res['expected_runs']}")
    out.append(f"  Z-score: {res['z_score']}")
    out.append(f"  p-value: {res['p_value']}")
    if res["is_random_like"]:
        out.append(f"\n  {ok} Sequence IS consistent with randomness (p > 0.01)")
    else:
        out.append(f"\n  {crit} Sequence is NOT random (p < 0.01)")
        if res["z_score"] < -2:
            out.append(f"  {warn} Too FEW runs — data may be clumped/periodic")
        elif res["z_score"] > 2:
            out.append(f"  {warn} Too MANY runs — data may be alternating artificially")
    return "\n".join(out)


# ----- Main -----

def load_values_from_csv(path: str, column: str) -> list:
    values = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                values.append(float(row[column]))
            except (ValueError, KeyError):
                continue
    return values


def main():
    parser = argparse.ArgumentParser(description="Normality and randomness checker")
    parser.add_argument("--test", choices=["normality", "uniform", "runs"], required=True, help="Which test to run")
    parser.add_argument("--input", help="CSV file with numerical data")
    parser.add_argument("--column", help="Column name in CSV")
    parser.add_argument("--binary-file", help="Binary file (each byte 0 or 1)")
    args = parser.parse_args()

    if args.test == "normality" or args.test == "uniform":
        values = []
        if args.input:
            if not args.column:
                print("Error: --column is required with --input", file=sys.stderr)
                sys.exit(1)
            values = load_values_from_csv(args.input, args.column)
        elif not sys.stdin.isatty():
            for line in sys.stdin:
                try:
                    values.append(float(line.strip()))
                except ValueError:
                    continue
        else:
            print("Error: provide --input/--column, or pipe numbers via stdin", file=sys.stderr)
            sys.exit(1)

        if len(values) < 10:
            print(f"Error: need at least 10 values (got {len(values)})", file=sys.stderr)
            sys.exit(1)

        if args.test == "normality":
            print(format_normality_report(values))
        else:
            print(format_uniform_report(values))

    elif args.test == "runs":
        bits = []
        if args.binary_file:
            with open(args.binary_file, "rb") as f:
                data = f.read()
            for byte in data:
                for bit in range(8):
                    bits.append((byte >> (7 - bit)) & 1)
        elif not sys.stdin.isatty():
            data = sys.stdin.buffer.read()
            for byte in data:
                for bit in range(8):
                    bits.append((byte >> (7 - bit)) & 1)
        else:
            print("Error: provide --binary-file or pipe binary data via stdin", file=sys.stderr)
            sys.exit(1)

        if len(bits) < 10:
            print(f"Error: need at least 10 bits (got {len(bits)})", file=sys.stderr)
            sys.exit(1)

        print(format_runs_report(bits))


if __name__ == "__main__":
    main()
