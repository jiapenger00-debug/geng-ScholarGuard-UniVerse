---
name: academic-fraud-detector
description: "Use when the user asks to analyze academic papers for fraud, data fabrication, image manipulation, plagiarism, or statistical anomalies across ANY discipline (STEM, social sciences, humanities, arts). Use when the user mentions 论文打假, 学术不端, 学术造假, 撤稿分析, 论文图片问题, 数据造假检测, 统计异常, peer review concerns, or wants to verify a paper's integrity. Also use when the user shares a paper DOI, PDF path, or academic webpage and asks 'is this legit?' or 'check this paper.'"
---

# 全科目学术论文打假检测器 (Academic Fraud Detector — All Disciplines)

## Overview

A systematic framework for detecting potential academic fraud in research papers across ALL disciplines — STEM, social sciences, humanities, and arts. Inspired by 耿同学讲故事's whistleblowing work and the original `geng-academic-fraud-detector` skill, but expanded from biomedicine-only to universal coverage.

**Core principle:** Academic fraud has discipline-specific forms, but the underlying patterns — lazy copying, impossible numbers, contradictory claims, and statistical manipulation — are universal. This skill teaches you to recognize those patterns regardless of field.

**Violating the letter of this detection process is violating the spirit of academic integrity verification.**

## The Iron Law

```
NO JUDGMENT WITHOUT EVIDENCE. NO ACCUSATION WITHOUT VERIFICATION.
```

Every finding MUST be traceable to specific, verifiable evidence in the source material. If you can't point to it, you don't have it.

## When to Use

Use this skill when the user:
- Shares a paper PDF, DOI, or academic URL and asks for verification
- Mentions retractions, academic fraud, data fabrication, or image manipulation
- Asks "is this paper legit?" or "does this data look fake?"
- Wants to audit a researcher's publication record
- Is a journal editor, peer reviewer, journalist, or researcher concerned about integrity
- Mentions specific fraud patterns: Western blot splicing, p-hacking, image reuse, citation rings

**Also use when the user doesn't explicitly ask but:**
- Is reading a paper critically and you spot red flags
- Is discussing a controversial or high-profile research finding
- Is working with data from a paper and something "feels off"

**Do NOT use for:**
- General literature review or summary (no fraud concern)
- Paper formatting or language editing
- Legitimate peer review of methodology (unless fraud indicators are present)

## Detection Workflow

You MUST follow this three-layer workflow in order. Each layer builds on the previous one.

```
┌─────────────────────────────────────────────────────┐
│  LAYER 1: Universal Scan (5-10 min)                │
│  Quick red flags, all disciplines                   │
│  ↓ IF FLAGS FOUND → continue to Layer 2             │
│  ↓ IF CLEAN → report "no obvious issues", stop      │
├─────────────────────────────────────────────────────┤
│  LAYER 2: Deep Discipline Scan (10-30 min)          │
│  Subject-specific checks, detailed analysis          │
│  ↓ COLLECT ALL FINDINGS → proceed to Layer 3        │
├─────────────────────────────────────────────────────┤
│  LAYER 3: Synthesis & Report                        │
│  Risk scoring, evidence chain, structured report     │
└─────────────────────────────────────────────────────┘
```

### Mode Selection

Ask the user (or infer from context):

- **Quick scan (快速筛查):** Layer 1 only. 5-10 minutes. Hit the highest-signal checks and flag anything suspicious. Good for initial triage.
- **Deep investigation (深度调查):** All three layers. 30+ minutes. Exhaustive analysis with evidence documentation. Good for formal challenges or retraction recommendations.

When the user doesn't specify, default to **quick scan** for group chats and first encounters; offer to go deeper if flags are found.

---

## Layer 1: Universal Scan (All Disciplines)

These checks apply to EVERY paper regardless of field. Run them all, even if some seem less relevant — fraudsters cut corners in predictable ways.

### 1.1 Text Integrity

**Plagiarism / 文本抄袭:**
- Search key sentences (10-15 word phrases, especially from the introduction and methods) on the web. Use WebSearch for 3-5 distinctive phrases.
- Check if the paper's title or abstract appears on other sites with different authors.
- Look for translation-as-original: Chinese-to-English or English-to-Chinese back-translation patterns.
- Pay special attention to literature review sections — these are the most commonly copy-pasted.

**Citation Fabrication / 引用捏造:**
- Spot-check 5-10 references: do the cited papers actually exist? Use WebSearch to verify.
- Check if cited papers actually say what the paper claims they say. Read the abstract of cited papers.
- Look for "phantom citations" — references with plausible-sounding titles that return zero search results.
- Flag over-citation of the same author (potential citation ring / 引用圈).

**AI Generation Markers:**
- Check for GPT/LLM artifacts: "As an AI language model...", "I don't have access to...", overly generic hedging language.
- Look for hallucinated references — AI-generated papers are notorious for inventing plausible but non-existent citations.
- Pay attention to unnatural uniformity in paragraph length and sentence structure.

### 1.2 Data Integrity

**Numerical Anomalies / 数值异常:**
- Check last-digit distribution (terminal digit analysis): in real data, the last digit should follow a roughly uniform distribution if the measurement precision is appropriate. An excess of round numbers (ending in 0 or 5) or missing certain digits suggests fabrication.
- Apply Benford's Law to leading digits when applicable (naturally occurring multi-order-of-magnitude numbers like population sizes, financial figures, chemical concentrations across orders of magnitude).
  - Use `scripts/benford.py` if available, or implement inline with Python.
  - **IMPORTANT:** Benford's Law does NOT apply to: small ranges (e.g., heights of adults), assigned numbers (IDs, phone numbers), or data with fixed bounds.
- Check for impossible precision: are measurements reported to more decimal places than the instrument can measure?
- Check for exact duplicates: identical means ± identical SDs across independent experiments is extremely unlikely.

**Statistical Sanity / 统计合理性:**
- Check if reported p-values match the reported test statistics. A common fabrication error: reporting t(28)=2.5, p=0.001 when the correct p for that t and df is ~0.019.
  - Use `scripts/stat_check.py` if available, or calculate inline with `scipy.stats`.
- Check for impossible p-values: p=0.000 (p-values are never exactly zero), p>1.0, or p-values that don't match the reported effect direction.
- Check degrees of freedom: do they match the stated sample size?
- Check if confidence intervals and p-values are consistent (e.g., CI that crosses zero but p<0.05).

**Sample / 样本问题:**
- Does the reported sample size match the degrees of freedom in statistical tests?
- Are there "vanishing subjects" — sample size changes between tables without explanation?
- Check for impossible recruitment rates: "recruited 500 rare-disease patients in 3 months from a single clinic."

### 1.3 Figure & Image Quick Check

**Image Integrity / 图片完整性:**
- Visually scan all figures for obvious duplication or manipulation.
- Check if the same image appears in multiple figures (possibly rotated, cropped, or brightness-adjusted).
- For papers with multiple experimental groups: do "different" samples look suspiciously identical?
- Check figure resolution consistency — different figures having vastly different resolutions or compression artifacts suggests copy-pasting from other sources.
- **RED FLAG:** Any figure where the background texture/pattern is identical between supposedly independent samples.

**Graph & Chart Issues:**
- Do error bars show impossible patterns? (all exactly the same height, no error bars at all on experimental data)
- Do data distributions look "too perfect"? Real biological/behavioral data is noisy.
- Check axis scales — are they manipulated to exaggerate or hide effects?
- Are there "dropped" data points without explanation?

### 1.4 Publication Pattern Anomalies

**产出异常 / Output Anomalies:**
- Check the author's publication frequency. Use WebSearch to find their publication record.
  - **RED FLAG:** More than 20 papers/year as first/corresponding author in experimental fields.
  - **EXTREME FLAG:** "硕士3年84篇SCI" or similar implausible numbers (referencing 耿同学's case).
- Look for "salami slicing" — splitting one study into multiple minimal publishable units.
- Check if the paper's content justifies a full paper vs. a short report or letter.

**Author Patterns:**
- Gift authorship: senior authors on papers far outside their expertise.
- Check for paper mills: many papers with similar structures, different first authors, same corresponding author.
- Sudden topic jumps: author switches between completely unrelated fields without collaboration.

### 1.5 Methodological Consistency

**方法一致性:**
- Do the methods describe what the results actually show? A common error: methods describe one analysis, but results show a different one.
- Timeline check: could the described experiments realistically be completed in the stated timeframe?
- Equipment availability: does the paper use equipment/instruments that the authors' institution likely has?
- Reagent/software version consistency: are the stated versions compatible with each other?

---

## Layer 2: Deep Discipline Scan

After Layer 1, identify the paper's primary discipline(s) and apply the relevant specialized checks below. A paper may span multiple disciplines — apply all relevant modules.

### 2.1 Biomedical / Life Sciences (生物医学)

**Image Duplication (图片复用) — 耿同学第一式:**
- Western blot bands: compare all blots across figures. Look for:
  - Identical band patterns in "different" experiments
  - Rotated or flipped images reused
  - Copied and pasted bands within the same blot
  - Background inconsistencies between lanes of the same blot
- Microscopy images: compare cell/tissue images across figures and conditions.
  - Same field of view claimed as different samples
  - Identical "representative" images across different experimental groups
- FACS/flow cytometry: compare scatter plots across conditions.
  - Identical dot patterns with different labels

**Western Blot Specific (耿同学第三式):**
- Check for splicing marks — straight vertical lines between lanes suggest lane splicing.
- Check loading controls: are the same loading control bands used for different experiments?
- Band intensity: do bands show expected patterns? (e.g., dose-response should show graded changes)
- Background: is the background consistent across all lanes of the same blot?

**Data Specific to Biomedicine:**
- Check n-numbers: animal studies should report exact n per group. Missing n-numbers = major red flag.
- Ethical approval: does the paper cite IACUC/IRB approval? Check if the approval number is valid.
- Clinical trials: verify registration on ClinicalTrials.gov or equivalent registry. Check if primary endpoints match.

### 2.2 Physical Sciences (物理/化学/材料)

**Spectral Data (谱图):**
- NMR: check if peaks match the reported structure. Use chemical shift prediction to verify.
- Mass spec: check if the molecular ion peak and fragmentation pattern match the reported compound.
- XRD: check if the pattern matches the claimed crystal structure. Compare with reference patterns.
- IR/Raman: verify characteristic peaks correspond to the reported functional groups.

**Chemical / Materials:**
- Yield reporting: are yields suspiciously perfect ("100% yield" for multi-step synthesis)?
- Elemental analysis: do reported values match calculated values within accepted error (±0.4%)?
- Reproducibility: are synthetic procedures described in sufficient detail to reproduce?

**Physics Specific:**
- Error analysis: are error bars appropriate for the measurement type? (systematic vs. statistical errors)
- Unit consistency: do units check out across calculations?
- Conservation laws: do reported results respect fundamental conservation laws?

### 2.3 Computer Science / Engineering (计算机/工程)

**Code & Algorithm:**
- Code availability: does the paper provide actual code, or only vague descriptions?
- Reproducibility: if code is provided, scan for hardcoded seeds, cherry-picked results, or hidden data leakage.
- Benchmark integrity: are benchmark results comparable to published baselines? Check if the paper uses the same train/test splits as prior work.
- **RED FLAG:** State-of-the-art claims without comparing against the actual SOTA methods.

**Result Manipulation:**
- Check for "test set training": suspiciously perfect results on standard benchmarks.
- Training/validation/test contamination: do the authors use the same data for multiple purposes?
- Check if ablation studies genuinely support claims or are cherry-picked.

**Image/Video Results:**
- For vision/graphics papers: compare generated images for artifacts of copy-pasting or dataset memorization.
- Check if "representative results" are actually the best-case cherry picks.

### 2.4 Social Sciences (社科/经管/心理)

**Survey & Questionnaire Data:**
- Response patterns: check for straight-lining (all 3s on a 5-point scale), Christmas-tree patterns, or impossibly fast completion times.
- Scale reliability: are Cronbach's alpha values suspiciously perfect (>0.95 for every scale)?
- Sample representativeness: does the sample match the claimed population? Check demographics.
- **RED FLAG:** "WEIRD" samples (Western, Educated, Industrialized, Rich, Democratic) claimed as universal — not fraud per se, but a validity concern.

**Econometric / Statistical:**
- Regression specifications: do control variables make sense? Check for "control variable mining."
- Instrument validity: for IV analyses, are the instruments defensible?
- p-hacking indicators: rounded p-values (p=0.049, p=0.051), many variables tested but only significant ones reported.
- Check if standard errors are clustered appropriately for the data structure.

**Psychology Specific:**
- Check for "optional stopping" — data collection stopped when p<0.05 was reached.
- "Researcher degrees of freedom" in analysis choices — too many undisclosed analytic decisions.
- Replication: has this finding been replicated? Check for replication studies.

### 2.5 Humanities (人文/历史/哲学/文学)

**Source Integrity:**
- Citation accuracy: spot-check 5-10 historical/archival citations. Do the cited sources exist?
- Textual evidence: for literary/historical analysis, verify that quoted passages are accurate and in context.
- Translation integrity: if the paper relies on translated sources, check if the translations are accurate or manipulated.

**Plagiarism Patterns:**
- Humanities papers are especially vulnerable to translation plagiarism (translating foreign-language work and presenting as original).
- Check for "mosaic plagiarism" — stitching together passages from multiple sources with minor rewording.
- Verify that attributed ideas actually come from the cited source.

**Argument Structure:**
- Logical gaps: does the conclusion follow from the evidence presented?
- Cherry-picked evidence: does the paper ignore obvious counterexamples or counterarguments?
- Circular reasoning: are conclusions assumed in the premises?

### 2.6 Mathematics (数学)

**Proof Integrity:**
- Check for logical leaps: "it is obvious that..." followed by a non-obvious claim.
- Theorem misapplication: are theorems applied under conditions where they don't hold?
- Counterexample search: try to construct a simple counterexample to the main claim.

**Computational Mathematics:**
- Numerical stability: can the claimed results be reproduced with standard numerical methods?
- Convergence claims: are convergence rates plausible for the stated problem class?

---

## Layer 3: Synthesis & Report

After completing Layers 1 and 2, synthesize all findings into a structured report.

### 3.1 Risk Scoring

Assign each finding a severity level:

| Level | Symbol | Description | Example |
|-------|--------|-------------|---------|
| **CRITICAL** | 🔴🔴🔴 | Definitive evidence of fabrication/falsification | Identical images with different labels |
| **HIGH** | 🔴🔴 | Strong indication; unlikely to be accidental | Impossible p-values, nonexistent citations |
| **MEDIUM** | 🔴 | Suspicious; needs further investigation | Unusual data patterns, statistical oddities |
| **LOW** | 🟡 | Minor concern; could be error rather than fraud | Rounding issues, minor inconsistencies |
| **INFO** | ℹ️ | Not fraud, but methodological concern | Small sample size, WEIRD sampling |

**Overall Risk Assessment:**
- **🔴🔴🔴 Critical Risk:** Multiple HIGH+ findings across independent dimensions → recommend formal investigation.
- **🔴🔴 High Risk:** 2+ HIGH findings or 5+ MEDIUM findings → serious concerns, warrants scrutiny.
- **🔴 Moderate Risk:** Some MEDIUM findings but no HIGH → possible issues, flag for review.
- **🟡 Low Risk:** Only LOW/INFO findings → no obvious fraud indicators.
- **✅ Clean:** No findings → paper passes initial screening.

### 3.2 Report Structure

ALWAYS use this exact report template:

```markdown
# Academic Fraud Detection Report

## Paper Information
- **Title:** [paper title]
- **Authors:** [authors]
- **Journal/Preprint:** [journal name or preprint server]
- **DOI:** [DOI if available]
- **Analysis Date:** [date]
- **Analysis Mode:** [Quick Scan / Deep Investigation]

## Executive Summary
[2-3 sentences summarizing the most important findings and overall risk level]

## Overall Risk Assessment: [🔴🔴🔴 / 🔴🔴 / 🔴 / 🟡 / ✅]

## Layer 1: Universal Scan Results

### 1.1 Text Integrity
[Findings with evidence]

### 1.2 Data Integrity
[Findings with evidence]

### 1.3 Figures & Images
[Findings with evidence]

### 1.4 Publication Patterns
[Findings with evidence]

### 1.5 Methodological Consistency
[Findings with evidence]

## Layer 2: Discipline-Specific Results
[For each applicable discipline module, list findings with evidence]

## Evidence Summary

| # | Finding | Layer | Severity | Evidence | Confidence |
|---|---------|-------|----------|----------|------------|
| 1 | [finding description] | [1/2] | [level] | [specific location in paper] | [High/Medium/Low] |
| ... | ... | ... | ... | ... | ... |

## Strengths
[What the paper does well — be fair and balanced. Not everything is fraud.]

## Limitations of This Analysis
- [What you couldn't check — e.g., raw data not available, images too low-res]
- [Methodological limitations of AI-based detection]
- [Other caveats]

## Recommendations
- [ ] [Specific action items, prioritized]
```

### 3.3 Reporting Principles

1. **Be specific.** "Figure 2A and Figure 5B appear to contain identical cell images (rotated 180°)" — not "some images look similar."
2. **Be fair.** Acknowledge innocent explanations where plausible. "This could be an honest labeling error, but warrants clarification."
3. **Be clear about confidence.** Distinguish between "this IS fraud" and "this LOOKS suspicious and should be investigated."
4. **Document what you CANNOT check.** Transparency about limitations builds credibility.
5. **NEVER claim certainty where there is doubt.** AI-based analysis is a screening tool, not a final verdict.

---

## Quick Reference: Red Flags by Discipline

### All Disciplines
- [ ] Key sentences found verbatim elsewhere on the web
- [ ] References that don't exist (phantom citations)
- [ ] p-values that don't match test statistics
- [ ] Impossible precision (more decimals than instrument allows)
- [ ] Suspiciously identical means/SDs across independent groups
- [ ] LLM-generated text artifacts
- [ ] Authors with implausible publication rates

### Biomedicine
- [ ] Identical image regions in "different" experiments
- [ ] Western blot lane splicing marks
- [ ] Same loading controls for different experiments
- [ ] Missing n-numbers in animal studies
- [ ] Unregistered clinical trials

### Physical Sciences
- [ ] NMR peaks inconsistent with structure
- [ ] Impossible yields (>100% or "100%" for multi-step)
- [ ] Elemental analysis outside acceptable error
- [ ] XRD pattern mismatch with claimed structure

### Computer Science
- [ ] SOTA claims without comparison to actual SOTA
- [ ] No code or data release
- [ ] Hardcoded seeds or data leakage indicators
- [ ] Suspiciously perfect benchmark results

### Social Sciences
- [ ] Survey straight-lining or patterned responses
- [ ] Cronbach's alpha >0.95 for everything
- [ ] Rounded p-values clustered just below 0.05
- [ ] Undisclosed researcher degrees of freedom

### Humanities
- [ ] Translated passages presented as original
- [ ] Cited sources that don't exist or don't say what's claimed
- [ ] Mosaic plagiarism across multiple uncited sources
- [ ] Circular reasoning in argument structure

### Mathematics
- [ ] "Obviously" concealing non-obvious logical gaps
- [ ] Theorems applied outside their stated conditions
- [ ] Numerical results irreproducible with standard methods

---

## Tools & Scripts

The `scripts/` directory contains helper tools for automated checks. **All scripts have pure-Python fallbacks** — no third-party dependencies are required, though `scipy`, `Pillow`, and `matplotlib` improve accuracy and capabilities when installed.

| Script | Purpose | Required Deps | Optional Deps |
|--------|---------|---------------|---------------|
| `scripts/benford.py` | Benford's Law analysis | None (pure Python) | `scipy` (precision), `matplotlib` (plot) |
| `scripts/image_similarity.py` | Perceptual hash comparison | None (MD5 fallback) | `Pillow` (rotation/crop detection) |
| `scripts/stat_check.py` | p-value, t-test, F-test verification | None (pure Python) | `scipy` (precision) |

To use a script (use `python` not `python3` — works on Windows, macOS, Linux):
```bash
python {{SKILL_DIR}}/scripts/benford.py --input data.csv --column "values"
python {{SKILL_DIR}}/scripts/stat_check.py --test t --df 28 --stat 2.5 --p 0.001
python {{SKILL_DIR}}/scripts/image_similarity.py --paper-dir ./figures/
```

On Windows, use `py` instead of `python` if `python` is not on PATH:
```bash
py scripts\benford.py --numbers "123,456,789,1024,2048,4096"
```

When a script is not available, implement the check inline using Python with standard libraries (`scipy.stats`, `PIL`, `numpy`). Document what you implement.

---

## Common Mistakes & Anti-Patterns

| Mistake | Why It's Wrong | What To Do Instead |
|---------|---------------|-------------------|
| Applying Benford's Law to everything | Only works on multi-order-of-magnitude naturally occurring numbers | Check the data type FIRST, explain why Benford's Law applies |
| "The data looks too clean" | Real data CAN be clean with proper methodology | Find specific statistical anomalies, not just impressions |
| Confusing error with fraud | Honest mistakes happen | Distinguish patterns (systematic fraud) from isolated errors |
| Over-relying on AI detection | AI can hallucinate analysis results | Every finding must be traceable to specific, verifiable evidence |
| Making accusations without evidence | Unethical and potentially defamatory | Always use "potential concerns" language; never claim certainty without proof |
| Focusing only on one dimension | Fraudsters may be careful in one area but sloppy in another | Run ALL Layer 1 checks; the weakest link reveals the pattern |
| Ignoring field norms | Some fields have different standards (e.g., p-value thresholds differ) | Research field-specific norms before flagging standard practices |
| "Quick scan = quick judgment" | Even a quick scan must be thorough within its scope | Run every Layer 1 check; don't skip items because you're "in a hurry" |

## Red Flags — STOP and Verify

If you catch yourself thinking:
- "This is obviously fraudulent" (before completing systematic analysis)
- "I don't need to check the math, the images are damning enough"
- "The author is a known fraudster, so this paper is probably fake too"
- "This is too complex for me to analyze"
- "I'll skip the report and just tell the user my conclusion"

**ALL of these mean: STOP. Return to the systematic process. Follow the workflow.**

## Real-World Impact

The original `geng-academic-fraud-detector` skill, focused on biomedicine, successfully detected:
- Image duplication across figures (Figure 1D/4A, Figure 2A/5A panel reuse)
- Identical raw data under different experimental labels
- Logical contradictions in experimental design

These findings matched a paper that was later officially retracted by PLOS ONE (doi:10.1371/journal.pone.0313446).

The expanded framework in this skill extends these detection capabilities to ALL academic disciplines, because fraud is not unique to biomedicine — only the specific techniques vary.

## References

- `references/discipline_guides.md` — Extended discipline-specific detection guides
- `references/statistical_checks.md` — Detailed statistical verification methods
- `references/image_forensics.md` — Advanced image manipulation detection techniques

Read these when you need deeper guidance on a specific discipline or technique.
