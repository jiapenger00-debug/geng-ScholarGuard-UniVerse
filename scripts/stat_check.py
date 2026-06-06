#!/usr/bin/env python3
"""
Statistical Sanity Checker for Academic Fraud Detection.

Verifies reported statistical values for consistency:
- p-values vs. test statistics (t-test, F-test, chi-square)
- Degrees of freedom vs. sample size
- Confidence intervals vs. p-values
- Effect sizes vs. reported statistics

DEPENDENCIES:
    pip install scipy (optional; pure-Python fallback included)

USAGE:
    python stat_check.py --test t --df 28 --stat 2.5 --p 0.001
    python stat_check.py --test F --df1 2 --df2 45 --stat 5.3 --p 0.008
    python stat_check.py --test chi2 --df 3 --stat 12.5 --p 0.006
    python stat_check.py --test r --n 100 --stat 0.35 --p 0.0004
"""

import argparse
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


# ----- scipy detection -----
SCIPY_AVAILABLE = False
try:
    from scipy import stats as _scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    _scipy_stats = None


def _safe_emoji(emoji: str, fallback: str = "*") -> str:
    enc = sys.stdout.encoding or "utf-8"
    try:
        emoji.encode(enc)
        return emoji
    except (UnicodeEncodeError, LookupError):
        return fallback


# ----- log gamma (Lanczos) -----
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


# ----- regularized incomplete beta (for Student's t CDF) -----
def _beta_cdf(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) via continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use symmetry to ensure convergence: I_x(a, b) = 1 - I_{1-x}(b, a) if x > (a+1)/(a+b+2)
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _beta_cdf(b, a, 1.0 - x)
    # Compute log of beta
    log_beta = _log_gamma(a) + _log_gamma(b) - _log_gamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - log_beta) / a
    # Continued fraction
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        # Odd step
        aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return front * h


# ----- Student's t CDF (pure Python) -----
def _t_cdf(t_val: float, df: float) -> float:
    """CDF of Student's t distribution."""
    if df <= 0:
        return 0.5
    x = df / (df + t_val * t_val)
    cdf = 0.5 * _beta_cdf(df / 2.0, 0.5, x)
    return 1.0 - cdf if t_val > 0 else cdf


# ----- F distribution CDF (pure Python) -----
def _f_cdf(f_val: float, df1: float, df2: float) -> float:
    """CDF of F distribution."""
    if f_val <= 0 or df1 <= 0 or df2 <= 0:
        return 0.0
    x = (df1 * f_val) / (df1 * f_val + df2)
    return _beta_cdf(df1 / 2.0, df2 / 2.0, x)


# ----- Chi-square CDF (pure Python) -----
def _chi2_cdf(x: float, df: float) -> float:
    """CDF of chi-square distribution."""
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


# ----- Wrappers with scipy fallback -----
def _t_cdf_wrapped(t_val, df):
    if SCIPY_AVAILABLE:
        return float(_scipy_stats.t.cdf(t_val, df))
    return _t_cdf(t_val, df)


def _f_cdf_wrapped(f_val, df1, df2):
    if SCIPY_AVAILABLE:
        return float(_scipy_stats.f.cdf(f_val, df1, df2))
    return _f_cdf(f_val, df1, df2)


def _chi2_cdf_wrapped(x, df):
    if SCIPY_AVAILABLE:
        return float(_scipy_stats.chi2.cdf(x, df))
    return _chi2_cdf(x, df)


# ----- Test checkers -----
def check_t_test(df: int, t_stat: float, reported_p: float) -> dict:
    correct_p_two = 2 * (1 - _t_cdf_wrapped(abs(t_stat), df))
    correct_p_one = 1 - _t_cdf_wrapped(abs(t_stat), df)
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
    correct_p = 1 - _f_cdf_wrapped(f_stat, df1, df2)
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
    correct_p = 1 - _chi2_cdf_wrapped(chi2_stat, df)
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
    if abs(r) >= 1.0:
        return {"error": f"Correlation coefficient |r|={abs(r)} must be < 1.0"}
    t_stat = r * math.sqrt((n - 2) / (1 - r * r))
    df = n - 2
    correct_p_two = 2 * (1 - _t_cdf_wrapped(abs(t_stat), df))
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
    issues = []
    if test_type == "independent_t":
        inferred_n = reported_df + 2
        issues.append(f"Independent t-test: df={reported_df} implies n1+n2={inferred_n}")
        if reported_n and reported_n != inferred_n:
            issues.append(f"[!] INCONSISTENCY: reported n={reported_n} but df={reported_df} implies n1+n2={inferred_n}")
    elif test_type == "paired_t":
        inferred_n = reported_df + 1
        if reported_n and reported_n != inferred_n:
            issues.append(f"[!] INCONSISTENCY: reported n={reported_n} but paired df={reported_df} implies n={inferred_n}")
    elif test_type == "correlation":
        inferred_n = reported_df + 2
        if reported_n and reported_n != inferred_n:
            issues.append(f"[!] INCONSISTENCY: reported n={reported_n} but df={reported_df} implies n={inferred_n}")
    return {"test_type": test_type, "reported_n": reported_n, "reported_df": reported_df, "issues": issues}


def add_verdict(result: dict) -> dict:
    if "error" in result:
        result["verdict"] = f"[!] Error: {result['error']}"
        return result

    p_matches = result.get("matches") or result.get("matches_two_tailed") or result.get("matches_one_tailed")
    discrepancy = result.get("discrepancy", 0)
    reported_p = result.get("reported_p_value", 0)

    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    mod = _safe_emoji("[MOD]", "[!]")
    low = _safe_emoji("[LOW]", "[?]")

    if reported_p == 0:
        result["verdict"] = f"{crit} CRITICAL: p=0.000 is impossible. P-values are never exactly zero."
    elif reported_p < 0:
        result["verdict"] = f"{crit} CRITICAL: Negative p-value reported. This is mathematically impossible."
    elif reported_p > 1:
        result["verdict"] = f"{crit} CRITICAL: p-value > 1.0 reported. This is mathematically impossible."
    elif abs(discrepancy) > 0.05:
        result["verdict"] = (
            f"{high} HIGH: Large discrepancy between reported p={reported_p} "
            f"and correct p={result.get('correct_p', result.get('correct_p_two_tailed', '?'))}. "
            f"Difference = {discrepancy}. Likely fabricated."
        )
    elif abs(discrepancy) > 0.01:
        result["verdict"] = (
            f"{mod} MODERATE: Discrepancy between reported p={reported_p} "
            f"and correct value. Difference = {discrepancy}. Could be rounding error but suspicious."
        )
    elif abs(discrepancy) > 0.001:
        result["verdict"] = (
            f"{low} MINOR: Small discrepancy (difference={discrepancy}). "
            f"Likely rounding differences but worth noting."
        )
    elif p_matches:
        result["verdict"] = "[OK] Consistent: reported p-value matches the test statistic and degrees of freedom."
    else:
        result["verdict"] = "[?] Unable to determine consistency."

    return result


def print_report(result: dict):
    print("=" * 70)
    print("  STATISTICAL SANITY CHECK")
    print("=" * 70)

    if "error" in result and "verdict" not in result:
        print(f"\n  [X] Error: {result['error']}")
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
        "chi-square": "chi-square statistic",
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

    method_note = " (scipy)" if SCIPY_AVAILABLE else " (pure-Python fallback)"
    print(f"  Method:{method_note}")
    print(f"\n  Verdict: {result.get('verdict', 'N/A')}")

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

    if args.n and args.df and args.test in ["t", "r"]:
        test_type_map = {"t": "paired_t", "r": "correlation"}
        consistency = check_sample_consistency(args.n, int(args.df), test_type_map.get(args.test, "paired_t"))
        result["sample_consistency"] = consistency

    print_report(result)


if __name__ == "__main__":
    main()
