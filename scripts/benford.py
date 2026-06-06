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

USAGE:
    python benford.py --input data.csv --column "values"
    python benford.py --input data.csv --column "values" --plot
    python benford.py --numbers "123,456,789,1024,2048,4096"
"""

import argparse
import csv
import math
import sys
from collections import Counter


def leading_digit(n: float) -> int:
    """Extract the leading digit (1-9) from a positive number."""
    if n <= 0:
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


def chi_square_test(observed: dict, expected: dict, n: int) -> tuple:
    """
    Perform chi-square goodness-of-fit test against Benford's Law.
    Returns (chi2_stat, p_value, deviations).
    """
    from scipy.stats import chi2

    chi2 = 0.0
    deviations = {}
    for d in range(1, 10):
        expected_count = expected[d] * n
        actual_count = observed.get(d, 0)
        if expected_count > 0:
            deviation = (actual_count - expected_count) / (expected_count ** 0.5) if expected_count > 0 else 0
            chi2 += (actual_count - expected_count) ** 2 / expected_count
            deviations[d] = {
                "expected_pct": round(expected[d] * 100, 2),
                "actual_pct": round(actual_count / n * 100, 2) if n > 0 else 0,
                "expected_count": round(expected_count, 1),
                "actual_count": actual_count,
                "z_score": round(deviation, 2),
            }

    p_value = 1 - chi2.cdf(chi2, df=8)
    return chi2, p_value, deviations


def mad_test(observed: dict, expected: dict, n: int) -> float:
    """
    Mean Absolute Deviation (MAD) test.
    MAD > 0.015 is considered suspicious (Nigrini, 2012).
    """
    mad = sum(abs(observed.get(d, 0) / n - expected[d]) for d in range(1, 10)) / 9
    return mad


def analyze_numbers(numbers: list, plot: bool = False) -> dict:
    """Main analysis function."""
    digits = [d for n in numbers if (d := leading_digit(n)) is not None]
    n = len(digits)

    if n < 50:
        return {
            "error": f"Insufficient data: only {n} valid numbers with leading digits 1-9. Need at least 50 for reliable analysis.",
            "n": n,
        }

    observed = Counter(digits)
    expected = benford_expected()

    chi2_stat, p_value, deviations = chi_square_test(observed, expected, n)
    mad = mad_test(observed, expected, n)

    # Interpretation
    if p_value < 0.01:
        conformity = "🔴 SIGNIFICANT DEVIATION from Benford's Law (p < 0.01). Data may be fabricated."
    elif p_value < 0.05:
        conformity = "🔴 Deviates from Benford's Law (p < 0.05). Suspicious."
    elif p_value < 0.10:
        conformity = "🟡 Marginal deviation from Benford's Law (p < 0.10). Worth further scrutiny."
    else:
        conformity = "✅ Consistent with Benford's Law (p >= 0.10)."

    if mad > 0.015:
        conformity += f" MAD = {mad:.4f} (>0.015 threshold) also indicates non-conformity."

    result = {
        "n": n,
        "chi2_statistic": round(chi2_stat, 3),
        "p_value": round(p_value, 4),
        "mad": round(mad, 4),
        "conformity": conformity,
        "digit_distribution": {d: deviations[d] for d in range(1, 10)},
    }

    return result


def print_report(result: dict):
    """Pretty-print analysis results."""
    print("=" * 70)
    print("  BENFORD'S LAW ANALYSIS")
    print("=" * 70)
    print(f"\n  Sample size (n): {result.get('n', 'N/A')}")

    if "error" in result:
        print(f"\n  ❌ {result['error']}")
        return

    print(f"  Chi-square statistic: {result['chi2_statistic']}")
    print(f"  p-value: {result['p_value']}")
    print(f"  MAD (Mean Absolute Deviation): {result['mad']}")
    print(f"\n  Conclusion: {result['conformity']}\n")

    # Distribution table
    print(f"  {'Digit':<8} {'Expected %':<12} {'Actual %':<10} {'Expected N':<12} {'Actual N':<10} {'Z-score':<10}")
    print("  " + "-" * 62)
    for d in range(1, 10):
        dd = result["digit_distribution"][d]
        flag = " ⚠️" if abs(dd["z_score"]) > 2.0 else ""
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
            plt.savefig("benford_plot.png", dpi=150)
            print("\n  📊 Plot saved to: benford_plot.png")
        except ImportError:
            print("\n  ⚠️ matplotlib not available. Install with: pip install matplotlib")


if __name__ == "__main__":
    main()
