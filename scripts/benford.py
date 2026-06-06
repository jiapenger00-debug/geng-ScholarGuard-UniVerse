#!/usr/bin/env python3
"""
Benford's Law Analysis for Academic Fraud Detection.

Benford's Law states that in naturally occurring multi-order-of-magnitude
datasets, the leading digit d (1-9) appears with probability:
    P(d) = log10(1 + 1/d)

This script tests whether a column of numbers follows Benford's Law.
Significant deviations may indicate fabrication.

IMPORTANT: Benford's Law does NOT apply to:
- Small-range data (e.g., human heights: 150-200 cm)
- Assigned numbers (IDs, phone numbers, zip codes)
- Data with fixed bounds (percentages, proportions)
- Data with a built-in minimum or maximum

DEPENDENCIES:
    pip install scipy matplotlib (optional, both have graceful fallbacks)

USAGE:
    python benford.py --input data.csv --column "values"
    python benford.py --input data.csv --column "values" --plot
    python benford.py --numbers "123,456,789,1024,2048,4096"
"""

import argparse
import csv
import math
import os
import sys

# Force UTF-8 output on Windows (fixes emoji crash on GBK console)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        # Python < 3.7 fallback (shouldn't happen but safe)
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _safe_emoji(emoji: str, fallback: str = "*") -> str:
    """Return emoji if the output stream supports it, else fallback."""
    enc = sys.stdout.encoding or "utf-8"
    try:
        emoji.encode(enc)
        return emoji
    except (UnicodeEncodeError, LookupError):
        return fallback


# Try to import scipy; fall back to pure-python implementation if unavailable
SCIPY_AVAILABLE = False
try:
    from scipy.stats import chi2 as _scipy_chi2
    SCIPY_AVAILABLE = True
except ImportError:
    _scipy_chi2 = None


def _chi2_sf_pure(x: float, df: int) -> float:
    """
    Pure-Python survival function (1 - CDF) for chi-square distribution.
    Uses regularized upper incomplete gamma function.
    Less accurate than scipy near the tails but adequate for fraud screening.
    """
    # P(X > x) for chi-square with df
    # = Q(df/2, x/2) where Q is regularized upper incomplete gamma
    half_df = df / 2.0
    half_x = x / 2.0

    # Compute via series expansion
    if half_x < half_df + 1:
        # Use P(X <= x) = P(half_df, half_x) regularized lower
        # then 1 - that
        return 1.0 - _lower_gamma_reg(half_df, half_x)
    else:
        # Use upper directly (faster for large x)
        return _upper_gamma_reg(half_df, half_x)


def _lower_gamma_reg(a: float, x: float) -> float:
    """Regularized lower incomplete gamma function P(a, x)."""
    if x < 0 or a <= 0:
        return 0.0
    if x == 0:
        return 0.0

    # Use series expansion
    if x < a + 1:
        return _gamma_series(a, x)
    else:
        return 1.0 - _gamma_continued_fraction(a, x)


def _upper_gamma_reg(a: float, x: float) -> float:
    """Regularized upper incomplete gamma function Q(a, x) = 1 - P(a, x)."""
    return 1.0 - _lower_gamma_reg(a, x)


def _gamma_series(a: float, x: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    """Series expansion of regularized lower incomplete gamma for x < a+1."""
    if x == 0:
        return 0.0
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
    """Continued fraction expansion for x > a+1."""
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


def _log_gamma(x: float) -> float:
    """Lanczos approximation for log(Gamma(x))."""
    # Coefficients from Numerical Recipes
    cof = [
        76.18009172947146,
        -86.50532032941677,
        24.01409824083091,
        -1.231739572450155,
        0.1208650973866179e-2,
        -0.5395239384953e-5,
    ]
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in cof:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def leading_digit(n: float):
    """Extract the leading digit (1-9) from a positive number. Returns None for invalid input."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    if n <= 0 or math.isnan(n) or math.isinf(n):
        return None
    # Handle scientific notation and very small numbers
    while n < 1:
        n *= 10
    while n >= 10:
        n /= 10
    return int(n)


def benford_expected() -> dict:
    """Return expected Benford probabilities for digits 1-9."""
    return {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def chi_square_test(observed: dict, expected: dict, n: int):
    """
    Perform chi-square goodness-of-fit test against Benford's Law.
    Returns (chi2_stat, p_value, deviations).
    """
    chi2 = 0.0
    deviations = {}
    for d in range(1, 10):
        expected_count = expected[d] * n
        actual_count = observed.get(d, 0)
        if expected_count > 0:
            deviation = (actual_count - expected_count) / (expected_count ** 0.5)
            chi2 += (actual_count - expected_count) ** 2 / expected_count
        else:
            deviation = 0
        deviations[d] = {
            "expected_pct": round(expected[d] * 100, 2),
            "actual_pct": round(actual_count / n * 100, 2) if n > 0 else 0,
            "expected_count": round(expected_count, 1),
            "actual_count": actual_count,
            "z_score": round(deviation, 2),
        }

    if SCIPY_AVAILABLE:
        p_value = 1 - _scipy_chi2.cdf(chi2, df=8)
    else:
        p_value = _chi2_sf_pure(chi2, df=8)

    return chi2, p_value, deviations


def mad_test(observed: dict, expected: dict, n: int) -> float:
    """
    Mean Absolute Deviation (MAD) test.
    MAD > 0.015 is considered suspicious (Nigrini, 2012).
    """
    if n == 0:
        return 0.0
    mad = sum(abs(observed.get(d, 0) / n - expected[d]) for d in range(1, 10)) / 9
    return mad


def analyze_numbers(numbers: list) -> dict:
    """Main analysis function."""
    digits = []
    for n in numbers:
        ld = leading_digit(n)
        if ld is not None:
            digits.append(ld)
    n = len(digits)

    if n < 50:
        x = _safe_emoji("[X]", "[!]")
        return {
            "error": f"Insufficient data: only {n} valid numbers with leading digits 1-9. Need at least 50 for reliable analysis.",
            "n": n,
        }

    observed = {d: 0 for d in range(1, 10)}
    for d in digits:
        observed[d] += 1

    expected = benford_expected()
    chi2_stat, p_value, deviations = chi_square_test(observed, expected, n)
    mad = mad_test(observed, expected, n)

    # Interpretation with platform-safe emoji
    red = _safe_emoji("[RED]", "[!]")
    yellow = _safe_emoji("[YELLOW]", "[?]")
    green = _safe_emoji("[OK]", "[+]")

    if p_value < 0.01:
        conformity = f"{red} SIGNIFICANT DEVIATION from Benford's Law (p < 0.01). Data may be fabricated."
    elif p_value < 0.05:
        conformity = f"{red} Deviates from Benford's Law (p < 0.05). Suspicious."
    elif p_value < 0.10:
        conformity = f"{yellow} Marginal deviation from Benford's Law (p < 0.10). Worth further scrutiny."
    else:
        conformity = f"{green} Consistent with Benford's Law (p >= 0.10)."

    if mad > 0.015:
        conformity += f" MAD = {mad:.4f} (>0.015 threshold) also indicates non-conformity."

    # Append note about scipy fallback
    method_note = " (scipy)" if SCIPY_AVAILABLE else " (pure-Python chi-square)"
    conformity += f"  [Method: {method_note.strip()}]"

    return {
        "n": n,
        "chi2_statistic": round(chi2_stat, 3),
        "p_value": round(p_value, 4),
        "mad": round(mad, 4),
        "conformity": conformity,
        "digit_distribution": {d: deviations[d] for d in range(1, 10)},
    }


def print_report(result: dict):
    """Pretty-print analysis results."""
    print("=" * 70)
    print("  BENFORD'S LAW ANALYSIS")
    print("=" * 70)
    print(f"\n  Sample size (n): {result.get('n', 'N/A')}")

    if "error" in result:
        x = _safe_emoji("[X]", "[!]")
        print(f"\n  {x} {result['error']}")
        return

    print(f"  Chi-square statistic: {result['chi2_statistic']}")
    print(f"  p-value: {result['p_value']}")
    print(f"  MAD (Mean Absolute Deviation): {result['mad']}")
    print(f"\n  Conclusion: {result['conformity']}\n")

    # Distribution table
    print(f"  {'Digit':<8} {'Expected %':<12} {'Actual %':<10} {'Expected N':<12} {'Actual N':<10} {'Z-score':<10}")
    print("  " + "-" * 62)
    warn = _safe_emoji("[!]", "*")
    for d in range(1, 10):
        dd = result["digit_distribution"][d]
        flag = f" {warn}" if abs(dd["z_score"]) > 2.0 else ""
        print(f"  {d:<8} {dd['expected_pct']:<12} {dd['actual_pct']:<10} {dd['expected_count']:<12} {dd['actual_count']:<10} {dd['z_score']:<10}{flag}")


def main():
    parser = argparse.ArgumentParser(description="Benford's Law analysis for fraud detection")
    parser.add_argument("--input", help="CSV file with numerical data")
    parser.add_argument("--column", help="Column name in CSV to analyze")
    parser.add_argument("--numbers", help="Comma-separated list of numbers")
    parser.add_argument("--plot", action="store_true", help="Generate a plot (requires matplotlib)")
    args = parser.parse_args()

    numbers = []

    if args.numbers:
        numbers = [float(x.strip()) for x in args.numbers.split(",") if x.strip()]
    elif args.input and args.column:
        with open(args.input, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    numbers.append(float(row[args.column]))
                except (ValueError, KeyError):
                    continue
    else:
        # Read from stdin: one number per line
        for line in sys.stdin:
            try:
                numbers.append(float(line.strip()))
            except ValueError:
                continue

    if not numbers:
        print("Error: No valid numbers provided.", file=sys.stderr)
        print("Usage: python benford.py --input data.csv --column 'values'", file=sys.stderr)
        print("       python benford.py --numbers '123,456,789,1024'", file=sys.stderr)
        sys.exit(1)

    result = analyze_numbers(numbers)
    print_report(result)

    if args.plot and "error" not in result:
        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend for headless env
            import matplotlib.pyplot as plt

            digits = list(range(1, 10))
            expected_vals = [result["digit_distribution"][d]["expected_pct"] for d in digits]
            actual_vals = [result["digit_distribution"][d]["actual_pct"] for d in digits]

            fig, ax = plt.subplots(figsize=(10, 5))
            x = range(len(digits))
            width = 0.35
            ax.bar([i - width / 2 for i in x], expected_vals, width, label="Benford's Law (Expected)", alpha=0.8)
            ax.bar([i + width / 2 for i in x], actual_vals, width, label="Observed", alpha=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels([str(d) for d in digits])
            ax.set_xlabel("Leading Digit")
            ax.set_ylabel("Percentage (%)")
            ax.set_title(f"Benford's Law Analysis (n={result['n']}, p={result['p_value']})")
            ax.legend()
            plt.tight_layout()
            output_path = os.path.join(os.getcwd(), "benford_plot.png")
            plt.savefig(output_path, dpi=150)
            print(f"\n  Plot saved to: {output_path}")
        except ImportError:
            print("\n  matplotlib not available. Install with: pip install matplotlib")


if __name__ == "__main__":
    main()
