#!/usr/bin/env python3
"""
Statistical Sanity Checker for Academic Fraud Detection.

Verifies reported statistical values for consistency:
- p-values vs. test statistics (t-test, F-test, chi-square)
- Degrees of freedom vs. sample size
- Confidence intervals vs. p-values
- Effect sizes vs. reported statistics

USAGE:
    python stat_check.py --test t --df 28 --stat 2.5 --p 0.001
    python stat_check.py --test F --df1 2 --df2 45 --stat 5.3 --p 0.008
    python stat_check.py --test chi2 --df 3 --stat 12.5 --p 0.006
    python stat_check.py --test r --n 100 --stat 0.35 --p 0.0004
"""

import argparse
import math
import sys


def check_t_test(df: int, t_stat: float, reported_p: float) -> dict:
    """Verify a reported t-test result."""
    try:
        from scipy.stats import t
        correct_p_two = 2 * (1 - t.cdf(abs(t_stat), df))
        correct_p_one = 1 - t.cdf(abs(t_stat), df)
    except ImportError:
        return {"error": "scipy not available. Install with: pip install scipy"}

    return {
        "test": "t-test",
        "df": df,
        "reported_statistic": t_stat,
        "reported_p_value": reported_p,
        "correct_p_two_tailed": round(correct_p_two, 6),
        "correct_p_one_tailed": round(correct_p_one, 6),
        "matches_two_tailed": abs(correct_p_two - reported_p) < 0.001,
        "matches_one_tailed": abs(correct_p_one - reported_p) < 0.001,
        "discrepancy": round(reported_p - correct_p_two, 6),
        "verdict": "",
    }


def check_f_test(df1: int, df2: int, f_stat: float, reported_p: float) -> dict:
    """Verify a reported F-test result (ANOVA)."""
    try:
        from scipy.stats import f
        correct_p = 1 - f.cdf(f_stat, df1, df2)
    except ImportError:
        return {"error": "scipy not available. Install with: pip install scipy"}

    return {
        "test": "F-test",
        "df1": df1,
        "df2": df2,
        "reported_statistic": f_stat,
        "reported_p_value": reported_p,
        "correct_p": round(correct_p, 6),
        "matches": abs(correct_p - reported_p) < 0.001,
        "discrepancy": round(reported_p - correct_p, 6),
        "verdict": "",
    }


def check_chi2_test(df: int, chi2_stat: float, reported_p: float) -> dict:
    """Verify a reported chi-square test result."""
    try:
        from scipy.stats import chi2
        correct_p = 1 - chi2.cdf(chi2_stat, df)
    except ImportError:
        return {"error": "scipy not available. Install with: pip install scipy"}

    return {
        "test": "chi-square",
        "df": df,
        "reported_statistic": chi2_stat,
        "reported_p_value": reported_p,
        "correct_p": round(correct_p, 6),
        "matches": abs(correct_p - reported_p) < 0.001,
        "discrepancy": round(reported_p - correct_p, 6),
        "verdict": "",
    }


def check_correlation(n: int, r: float, reported_p: float) -> dict:
    """Verify a reported Pearson correlation p-value."""
    try:
        from scipy.stats import t
        if abs(r) >= 1.0:
            return {"error": f"Correlation coefficient |r|={abs(r)} must be < 1.0"}
        t_stat = r * math.sqrt((n - 2) / (1 - r * r))
        df = n - 2
        correct_p_two = 2 * (1 - t.cdf(abs(t_stat), df))
    except ImportError:
        return {"error": "scipy not available. Install with: pip install scipy"}

    return {
        "test": "Pearson correlation",
        "n": n,
        "df": df,
        "reported_r": r,
        "derived_t_statistic": round(t_stat, 4),
        "reported_p_value": reported_p,
        "correct_p_two_tailed": round(correct_p_two, 6),
        "matches": abs(correct_p_two - reported_p) < 0.001,
        "discrepancy": round(reported_p - correct_p_two, 6),
        "verdict": "",
    }


def check_sample_consistency(reported_n: int, reported_df: int, test_type: str) -> dict:
    """
    Check if reported sample size is consistent with degrees of freedom.
    Common patterns:
    - Independent t-test: df = n1 + n2 - 2
    - Paired t-test: df = n - 1
    - One-way ANOVA: df_between = k-1, df_within = N-k
    - Correlation: df = n - 2
    - Chi-square: df = (r-1)(c-1), independent of n
    """
    issues = []

    if test_type == "independent_t":
        inferred_n = reported_df + 2
        issues.append(f"Independent t-test: df={reported_df} implies n1+n2={inferred_n}")
        if reported_n and reported_n != inferred_n:
            issues.append(f"🔴 INCONSISTENCY: reported n={reported_n} but df={reported_df} implies n1+n2={inferred_n}")

    elif test_type == "paired_t":
        inferred_n = reported_df + 1
        if reported_n and reported_n != inferred_n:
            issues.append(f"🔴 INCONSISTENCY: reported n={reported_n} but paired df={reported_df} implies n={inferred_n}")

    elif test_type == "correlation":
        inferred_n = reported_df + 2
        if reported_n and reported_n != inferred_n:
            issues.append(f"🔴 INCONSISTENCY: reported n={reported_n} but df={reported_df} implies n={inferred_n}")

    return {"test_type": test_type, "reported_n": reported_n, "reported_df": reported_df, "issues": issues}


def add_verdict(result: dict) -> dict:
    """Add a human-readable verdict to the check result."""
    if "error" in result:
        result["verdict"] = f"⚠️ Error: {result['error']}"
        return result

    # Check p-value matching
    p_matches = result.get("matches") or result.get("matches_two_tailed") or result.get("matches_one_tailed")
    discrepancy = result.get("discrepancy", 0)
    reported_p = result.get("reported_p_value", 0)

    # Check for impossible p-values
    if reported_p == 0:
        result["verdict"] = "🔴🔴🔴 CRITICAL: p=0.000 is impossible. P-values are never exactly zero."
    elif reported_p < 0:
        result["verdict"] = "🔴🔴🔴 CRITICAL: Negative p-value reported. This is mathematically impossible."
    elif reported_p > 1:
        result["verdict"] = "🔴🔴🔴 CRITICAL: p-value > 1.0 reported. This is mathematically impossible."
    elif abs(discrepancy) > 0.05:
        result["verdict"] = (
            f"🔴🔴 HIGH: Large discrepancy between reported p={reported_p} "
            f"and correct p={result.get('correct_p', result.get('correct_p_two_tailed', '?'))}. "
            f"Difference = {discrepancy}. Likely fabricated."
        )
    elif abs(discrepancy) > 0.01:
        result["verdict"] = (
            f"🔴 MODERATE: Discrepancy between reported p={reported_p} "
            f"and correct value. Difference = {discrepancy}. Could be rounding error but suspicious."
        )
    elif abs(discrepancy) > 0.001:
        result["verdict"] = (
            f"🟡 MINOR: Small discrepancy (difference={discrepancy}). "
            f"Likely rounding differences but worth noting."
        )
    elif p_matches:
        result["verdict"] = "✅ Consistent: reported p-value matches the test statistic and degrees of freedom."
    else:
        result["verdict"] = "⚠️ Unable to determine consistency."

    return result


def print_report(result: dict):
    """Pretty-print the check result."""
    print("=" * 70)
    print("  STATISTICAL SANITY CHECK")
    print("=" * 70)

    if "error" in result and "verdict" not in result:
        print(f"\n  ❌ Error: {result['error']}")
        return

    test_name = result.get("test", "Unknown test")
    print(f"\n  Test type: {test_name}")

    if "df" in result:
        print(f"  Degrees of freedom: {result['df']}")
    if "df1" in result:
        print(f"  df1={result['df1']}, df2={result['df2']}")
    if "n" in result:
        print(f"  Sample size (n): {result['n']}")

    stat_label = {
        "t-test": "t-statistic",
        "F-test": "F-statistic",
        "chi-square": "χ² statistic",
        "Pearson correlation": "Pearson r",
    }.get(test_name, "Statistic")

    print(f"  Reported {stat_label}: {result.get('reported_statistic', result.get('reported_r', 'N/A'))}")
    print(f"  Reported p-value: {result.get('reported_p_value', 'N/A')}")

    if "correct_p" in result:
        print(f"  Correct p-value: {result['correct_p']}")
    if "correct_p_two_tailed" in result:
        print(f"  Correct p (two-tailed): {result['correct_p_two_tailed']}")
    if "correct_p_one_tailed" in result:
        print(f"  Correct p (one-tailed): {result['correct_p_one_tailed']}")

    print(f"\n  📋 Verdict: {result.get('verdict', 'N/A')}")

    # Sample consistency check if applicable
    if "issues" in result:
        for issue in result["issues"]:
            print(f"  {issue}")


def main():
    parser = argparse.ArgumentParser(description="Verify reported statistical values for fraud detection")
    parser.add_argument("--test", required=True, choices=["t", "F", "chi2", "r"], help="Type of statistical test")
    parser.add_argument("--df", type=float, help="Degrees of freedom")
    parser.add_argument("--df1", type=float, help="Numerator degrees of freedom (F-test)")
    parser.add_argument("--df2", type=float, help="Denominator degrees of freedom (F-test)")
    parser.add_argument("--stat", type=float, help="Test statistic value")
    parser.add_argument("--p", type=float, required=True, help="Reported p-value")
    parser.add_argument("--n", type=int, help="Reported sample size (for correlation test or sample consistency check)")
    args = parser.parse_args()

    try:
        from scipy import stats  # noqa: F401
    except ImportError:
        print("Error: scipy is required. Install with: pip install scipy", file=sys.stderr)
        sys.exit(1)

    result = {}

    if args.test == "t":
        if args.df is None or args.stat is None:
            print("Error: t-test requires --df and --stat", file=sys.stderr)
            sys.exit(1)
        result = check_t_test(int(args.df), args.stat, args.p)

    elif args.test == "F":
        if args.df1 is None or args.df2 is None or args.stat is None:
            print("Error: F-test requires --df1, --df2, and --stat", file=sys.stderr)
            sys.exit(1)
        result = check_f_test(int(args.df1), int(args.df2), args.stat, args.p)

    elif args.test == "chi2":
        if args.df is None or args.stat is None:
            print("Error: chi-square test requires --df and --stat", file=sys.stderr)
            sys.exit(1)
        result = check_chi2_test(int(args.df), args.stat, args.p)

    elif args.test == "r":
        if args.n is None or args.stat is None:
            print("Error: correlation test requires --n and --stat (r value)", file=sys.stderr)
            sys.exit(1)
        result = check_correlation(args.n, args.stat, args.p)

    result = add_verdict(result)

    # Optionally check sample consistency
    if args.n and args.df and args.test in ["t", "r"]:
        test_type_map = {"t": "paired_t", "r": "correlation"}
        consistency = check_sample_consistency(args.n, int(args.df), test_type_map.get(args.test, "paired_t"))
        result["sample_consistency"] = consistency

    print_report(result)


if __name__ == "__main__":
    main()
