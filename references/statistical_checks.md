# Statistical Verification Methods

Reference for detailed statistical checks beyond basic p-value verification.

## P-Value Verification

### Why This Matters

A common fabrication error: researchers report plausible-sounding test statistics and p-values, but the p-value doesn't actually match the test statistic and degrees of freedom. This happens because:
1. They don't know how to compute p-values correctly
2. They copy statistics from another paper without understanding them
3. They fabricate numbers that "look right" without verification

### How to Verify

For any reported statistical test, reconstruct the p-value from the test statistic and df:

**t-test:** `p = 2 * (1 - t.cdf(|t_stat|, df))`
**F-test:** `p = 1 - f.cdf(F_stat, df1, df2)`
**Chi-square:** `p = 1 - chi2.cdf(χ², df)`
**Correlation:** `t = r * sqrt((n-2)/(1-r²))`, then t-test with `df = n-2`

Use `scripts/stat_check.py` or `scipy.stats` directly.

---

## Degrees of Freedom Analysis

### Common Patterns

Each statistical test has a known relationship between sample size and degrees of freedom:

| Test | df Formula | Example |
|------|-----------|---------|
| One-sample t-test | n - 1 | n=30 → df=29 |
| Independent t-test (equal var) | n₁ + n₂ - 2 | n₁=n₂=15 → df=28 |
| Paired t-test | n_pairs - 1 | 20 pairs → df=19 |
| One-way ANOVA (between) | k - 1 | 3 groups → df=2 |
| One-way ANOVA (within) | N - k | N=60, k=3 → df=57 |
| Pearson correlation | n - 2 | n=100 → df=98 |
| Chi-square (contingency) | (r-1)(c-1) | 2×3 table → df=2 |

If reported df doesn't match the stated sample size and test type, flag it.

---

## Impossible P-Values

These are immediate red flags that require no calculation:

| Reported | Why Impossible |
|----------|---------------|
| p = 0.000 | P-values are never exactly zero. Should be reported as p < 0.001 |
| p < 0 | Probabilities cannot be negative |
| p > 1 | Probabilities cannot exceed 1 |
| p = 0.05 exactly | Suspiciously convenient; real p-values have multiple decimals |
| Same p for every test | Every test result has the same p-value (suggests copy-paste) |

---

## Benford's Law — When to Use

### Appropriate Applications

Benford's Law applies to numbers that:
- Span multiple orders of magnitude
- Are NOT assigned (IDs, phone numbers, zip codes)
- Are NOT bounded (percentages, proportions)
- Are NOT human-influenced (prices set at $9.99)

**Good candidates:**
- Population counts across cities/countries
- Chemical concentrations across diverse samples
- Financial figures (budgets, grants)
- Physical measurements across wide ranges
- Genomic data (gene expression counts across genes)

### Inappropriate Applications (DO NOT USE)

- P-values (bounded 0-1)
- Percentages (bounded 0-100)
- Age/height/weight of humans (narrow range)
- Questionnaire scores (Likert scales: 1-5 or 1-7)
- Student IDs, patient IDs (assigned numbers)
- Correlation coefficients (bounded -1 to 1)

---

## Statistical Power and Sample Size

### Suspicious Patterns

**"Too good to be true" study designs:**
- Small sample detecting small effect: n=20, detecting d=0.2 with p<0.05 (requires n≈400 per group)
- Multiple significant results with tiny samples
- "Pilot studies" with n=10 that find p<0.001

**Power analysis check:**
For a reported effect size and sample size, compute the achieved power. If power < 0.5 for a significant result, flag as suspicious unless the effect is very large.

---

## Multivariate Pattern Checks

### Correlation Matrix Integrity

In a correlation matrix of k variables:
- The matrix must be positive semi-definite
- All diagonal elements must be 1.0
- The matrix must be symmetric
- Off-diagonal elements must be between -1 and 1

Fabricated correlation matrices often violate positive semi-definiteness because fabricators don't know this constraint exists.

### Regression Coefficient Consistency

- Standardized coefficients should be between approximately -1 and 1 (except in cases of high multicollinearity)
- Unstandardized coefficients should have realistic magnitudes given the variable scales
- R-squared change values should be positive and sum appropriately in hierarchical regression
