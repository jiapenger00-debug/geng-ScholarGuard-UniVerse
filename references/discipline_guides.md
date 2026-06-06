# Extended Discipline-Specific Detection Guides

## Table of Contents
1. [Biomedicine & Life Sciences](#biomedicine)
2. [Physics & Chemistry](#physics-chem)
3. [Computer Science & Engineering](#cs-eng)
4. [Social Sciences & Economics](#social-sci)
5. [Humanities](#humanities)
6. [Mathematics](#math)

---

## 1. Biomedicine & Life Sciences {#biomedicine}

### Western Blot Analysis — Deep Dive

Western blots are the single most commonly manipulated image type in biomedical fraud. Pay close attention to:

**Lane Splicing Detection:**
- Look for straight vertical lines between lanes where the background texture changes abruptly
- Check that lane spacing is uniform — spliced lanes often have irregular spacing
- Compare background noise patterns across lanes — real blots have continuous background texture

**Loading Control Reuse:**
- Authors often reuse the same β-actin/GAPDH loading control image across figures
- Compare all loading control bands across all figures in the paper
- Even if brightness/contrast is adjusted, band shape and relative position are preserved

**Band Morphology:**
- Real protein bands have slight asymmetry and fuzzy edges
- Perfectly rectangular, uniform-density bands suggest digital fabrication
- Check that band intensity follows expected patterns (dose-response curves should be monotonic)

### Flow Cytometry (FACS)

- "Different" scatter plots with identical dot distributions are a common fabrication
- Check the total event count — do all samples have exactly the same number of events?
- Gate percentages should sum appropriately

### Microscopy

- Identical "representative images" across conditions (possibly with color adjustments)
- Same cell cluster appearing in different experimental groups
- Check scale bars — inconsistent scale bars across "same magnification" images

### Clinical Research

- Verify trial registration: check ClinicalTrials.gov, ChiCTR, EU-CTR, etc.
- Primary endpoint switching: does the paper report the same primary endpoint as the registration?
- "Ghost patients": patient counts that don't add up across tables and flow diagrams

---

## 2. Physics & Chemistry {#physics-chem}

### Spectroscopy (NMR, IR, MS, XRD)

**NMR:**
- Peak multiplicity should match the proposed structure
- Integration ratios should match the number of protons
- Chemical shifts should be reasonable for the proposed functional groups
- Missing peaks: are there unexplained peaks or missing expected peaks?

**Mass Spectrometry:**
- Molecular ion peak must match the molecular formula
- Isotope pattern should match expected distribution (especially for Cl, Br-containing compounds)
- Fragmentation pattern should be chemically reasonable

**XRD:**
- Compare with reference patterns from databases (ICDD, ICSD)
- Peak positions, relative intensities, and peak widths should be consistent
- "Amorphous halo" patterns passed off as crystalline

### Synthetic Chemistry

- "100% yield" for multi-step synthesis is essentially impossible
- Check if reported yields are consistent with similar reactions in the literature
- Elemental analysis: C, H, N percentages should sum to ~100% (±0.4% for each element)
- Melting points: literature comparisons, sharp vs. broad melting ranges

### Physics

- Error analysis: systematic errors should be distinguished from statistical errors
- Sig fig consistency: results should have appropriate significant figures based on measurement precision
- Check if reported uncertainties are realistic for the measurement technique

---

## 3. Computer Science & Engineering {#cs-eng}

### Machine Learning Papers — Red Flag Checklist

**Data Leakage:**
- Train/test split done AFTER feature selection or normalization
- "Leave-one-subject-out" cross-validation not used when multiple samples per subject
- Temporal data split randomly instead of chronologically

**Benchmark Integrity:**
- Comparing against weak/outdated baselines while claiming SOTA
- Using different evaluation protocols than the baselines they compare against
- Reporting "best epoch" results on test set (should use validation set for model selection)

**Reproducibility:**
- No code release, or code that doesn't match the paper description
- Hardcoded random seeds that were clearly searched for best results
- Missing hyperparameter details that affect results

### Systems/Engineering Papers

- Performance claims that exceed theoretical hardware limits
- "Simulated" results presented as "experimental"
- Cherry-picked favorable conditions (ideal temperature, no interference)
- Missing error analysis on measurements

---

## 4. Social Sciences & Economics {#social-sci}

### Survey Research

**Response Quality:**
- Straight-lining: respondent selects same option for all questions
- Speeding: completion time < 1/3 of median
- Patterned responding: alternating or diagonal patterns
- Check for duplicate IP addresses or suspicious timing patterns

**Scale Construction:**
- Cronbach's alpha: >0.95 across ALL scales is suspicious (suggests redundant items or fabricated data)
- Factor analysis: do the factor loadings cleanly separate, or is there unexplained cross-loading?
- Check that reverse-coded items show appropriate negative correlations

### Econometrics

**Regression Diagnostics:**
- R-squared > 0.99 in cross-sectional social science data is essentially impossible
- Check if control variables are "convenient" (always significant, always in expected direction)
- Multiple hypothesis testing without correction (Bonferroni, Holm, FDR)

**Instrumental Variables:**
- Weak instruments: F-statistic < 10 in first stage
- Exclusion restriction: can the instrument affect the outcome ONLY through the endogenous variable?
- Overidentification tests: are they reported? Do they pass?

### Psychology

- "Questionable research practices" (QRPs) to look for:
  - Optional stopping (data collection terminated when p<0.05)
  - Selective reporting of dependent variables
  - Exclusion of participants based on post-hoc criteria
  - Transforming data to achieve significance
- Check for pre-registration and compare with reported analyses

---

## 5. Humanities {#humanities}

### Historical Research

- Verify archival citations: do the cited collections/boxes/folders exist?
- Check for anachronisms: terminology, concepts, or references that didn't exist in the claimed period
- Suspicious "discoveries": newly "found" documents that conveniently support the author's thesis
- Translation as original: presenting translated passages as original-language scholarship

### Literary Studies

- Quotation accuracy: do the quoted passages exactly match the source text?
- Context integrity: are quotes used in a way consistent with their original context?
- Citation games: citing obscure editions to make finding the source difficult

### Philosophy

- Straw man arguments: misrepresenting opposing views to make them easier to refute
- Term equivocation: using the same term with different meanings at different points in the argument
- Hidden premises: conclusions that require unstated (and potentially false) assumptions

### Law

- Case citation accuracy: do cited cases actually establish the claimed legal principles?
- Shepardize/KeyCite key citations — have they been overturned or questioned?
- Statutory interpretation: are statutes cited in their current, amended form?

---

## 6. Mathematics {#math}

### Proof Verification Approach

While AI cannot fully verify complex mathematical proofs, it can identify red flags:

**Structural Red Flags:**
- "It is obvious that..." or "clearly..." followed by a non-trivial claim
- Missing steps between major logical transitions
- Proof by intimidation: complex notation obscuring a simple error
- Circular reasoning: the conclusion is assumed in the proof

**Computational Red Flags:**
- Numerical results that can't be reproduced with standard libraries
- Convergence rates that contradict known theoretical bounds
- Algorithms claimed to solve NP-hard problems in polynomial time (unless P=NP is the claim)

### Applied Mathematics

- Model assumptions that don't match the application domain
- Dimensional analysis: do the equations balance dimensionally?
- Limiting cases: does the solution reduce to known results in special cases?
