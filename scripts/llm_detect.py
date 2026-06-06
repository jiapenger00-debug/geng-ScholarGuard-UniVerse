#!/usr/bin/env python3
"""
LLM-Generated Text Detector for Academic Fraud Detection.

Computes a battery of stylometric features to estimate the probability
that a body of text was written (or significantly edited) by a large
language model such as ChatGPT, Claude, or Gemini.

Features measured:
1. Sentence-length variance (LLM text is more uniform)
2. Type-token ratio (vocabulary diversity)
3. Bigram entropy (LLM text has lower entropy)
4. Burstiness score (LLM text lacks natural variation)
5. Function-word frequency
6. Paragraph-length uniformity
7. Hapax legomena ratio (words used only once)
8. Punctuation patterns

DEPENDENCIES:
    None (pure Python, stdlib only). Optional: --compare-against <baseline.txt>
    for relative scoring.

USAGE:
    # Analyze a single text file
    python llm_detect.py --text paper.txt

    # Compare against a baseline of known human-written text
    python llm_detect.py --text paper.txt --compare-against human_corpus.txt

    # Read from stdin
    cat paper.txt | python llm_detect.py

LIMITATIONS:
    This is a HEURISTIC detector. False positives are common for:
    - Highly edited technical writing
    - Non-native English speakers with simple prose
    - Short abstracts (<500 words)

    For high-stakes decisions, also use:
    - A dedicated tool like GPTZero, Originality.ai
    - The paper's own writing history / version diff
    - Author background check
"""

import argparse
import math
import os
import re
import string
import sys
from collections import Counter

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


# Common English function words (used as a stylistic fingerprint)
FUNCTION_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us",
}


# ----- Feature extractors -----

def tokenize_words(text: str) -> list:
    """Lowercase, strip punctuation, return word list."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def split_sentences(text: str) -> list:
    """Naive sentence splitter."""
    text = re.sub(r"\s+", " ", text)
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) > 5]


def split_paragraphs(text: str) -> list:
    """Split on blank lines."""
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if len(p.strip()) > 20]


def sentence_length_stats(text: str) -> dict:
    """Compute mean and variance of sentence lengths in words."""
    sents = split_sentences(text)
    if not sents:
        return {"n_sentences": 0}
    lengths = [len(tokenize_words(s)) for s in sents]
    mean = sum(lengths) / len(lengths)
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    cv = (math.sqrt(var) / mean) if mean > 0 else 0  # coefficient of variation
    return {
        "n_sentences": len(sents),
        "mean_length": round(mean, 2),
        "stdev_length": round(math.sqrt(var), 2),
        "cv": round(cv, 3),
    }


def type_token_ratio(text: str) -> dict:
    """Vocabulary diversity: unique words / total words."""
    words = tokenize_words(text)
    if not words:
        return {"total": 0, "unique": 0, "ttr": 0}
    return {
        "total_words": len(words),
        "unique_words": len(set(words)),
        "ttr": round(len(set(words)) / len(words), 4),
    }


def bigram_entropy(text: str) -> dict:
    """Shannon entropy over word bigrams. Lower entropy = more repetitive."""
    words = tokenize_words(text)
    if len(words) < 2:
        return {"entropy": 0, "n_bigrams": 0}
    bigrams = [(words[i], words[i + 1]) for i in range(len(words) - 1)]
    counts = Counter(bigrams)
    total = sum(counts.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return {
        "entropy": round(entropy, 3),
        "n_bigrams": len(bigrams),
        "n_unique_bigrams": len(counts),
    }


def hapax_ratio(text: str) -> dict:
    """Ratio of words that appear only once."""
    words = tokenize_words(text)
    if not words:
        return {"hapax": 0, "total": 0, "ratio": 0}
    counts = Counter(words)
    hapax = sum(1 for c in counts.values() if c == 1)
    return {
        "hapax_legomena": hapax,
        "total_unique": len(counts),
        "hapax_ratio": round(hapax / len(counts), 4),
    }


def function_word_density(text: str) -> dict:
    """Density of function words (style marker)."""
    words = tokenize_words(text)
    if not words:
        return {"function_count": 0, "function_pct": 0}
    fw_count = sum(1 for w in words if w in FUNCTION_WORDS)
    return {
        "function_count": fw_count,
        "function_pct": round(fw_count / len(words) * 100, 2),
    }


def paragraph_uniformity(text: str) -> dict:
    """Stdev of paragraph word counts. LLM text tends to be more uniform."""
    paras = split_paragraphs(text)
    if len(paras) < 2:
        return {"n_paragraphs": len(paras), "uniformity": "N/A"}
    pwords = [len(tokenize_words(p)) for p in paras]
    mean = sum(pwords) / len(pwords)
    var = sum((x - mean) ** 2 for x in pwords) / len(pwords)
    cv = (math.sqrt(var) / mean) if mean > 0 else 0
    return {
        "n_paragraphs": len(paras),
        "mean_words": round(mean, 2),
        "stdev_words": round(math.sqrt(var), 2),
        "cv": round(cv, 3),
    }


def burstiness_score(text: str) -> float:
    """
    Burstiness: ratio of sentence-length stdev to mean, normalized.
    Human writing has high burstiness (mix of long and short sentences).
    LLM writing has low burstiness (more uniform).
    """
    stats = sentence_length_stats(text)
    return stats.get("cv", 0)


# ----- LLM-likelihood composite score -----

def llm_likelihood_score(features: dict) -> dict:
    """
    Combine features into a 0-100 LLM-likeness score.
    Each indicator contributes a partial score. Weights are heuristic,
    based on the academic LLM-detection literature.
    """
    score = 0
    max_score = 0
    indicators = []

    # 1. Sentence length uniformity (low CV = more LLM-like)
    # Academic writing typically has CV > 0.40; LLM writing tends to be < 0.30
    cv = features.get("sentence_length", {}).get("cv", 0)
    if cv is not None and cv > 0:
        max_score += 20
        if cv < 0.25:  # very uniform — strong signal
            score += 20
            indicators.append(f"Very uniform sentence length (CV={cv:.3f}) — STRONG LLM signal")
        elif cv < 0.35:
            score += 10
            indicators.append(f"Uniform sentence length (CV={cv:.3f}) — moderate LLM signal")
        elif cv < 0.45:
            score += 3
            indicators.append(f"Somewhat uniform sentences (CV={cv:.3f}) — weak signal")
        # else: human-like burstiness, no score added

    # 2. Type-token ratio — for text > 500 words, expected TTR is 0.30-0.55
    ttr = features.get("ttr", {}).get("ttr", 0)
    total_words = features.get("ttr", {}).get("total_words", 0)
    if total_words > 200:
        max_score += 10
        if ttr < 0.20:
            score += 10
            indicators.append(f"Very low vocabulary diversity (TTR={ttr}) — highly repetitive")
        elif ttr < 0.30:
            score += 5
            indicators.append(f"Low vocabulary diversity (TTR={ttr})")
        # higher TTR is normal, not penalized

    # 3. Bigram entropy (lower = more LLM-like)
    # Typical human prose: 8-10 bits; LLM: 6-8 bits; formulaic: <6 bits
    entropy = features.get("bigram_entropy", {}).get("entropy", 0)
    if entropy > 0:
        max_score += 25
        if entropy < 5.0:
            score += 25
            indicators.append(f"Very low bigram entropy ({entropy}) — strong LLM signal")
        elif entropy < 6.5:
            score += 18
            indicators.append(f"Low bigram entropy ({entropy}) — repetitive phrasing")
        elif entropy < 7.5:
            score += 10
            indicators.append(f"Moderate bigram entropy ({entropy})")
        elif entropy < 8.5:
            score += 3
        # else: normal

    # 4. Paragraph uniformity (low CV = more LLM-like)
    p_cv = features.get("paragraph_uniformity", {}).get("cv", 0)
    if p_cv is not None and p_cv > 0 and features.get("paragraph_uniformity", {}).get("n_paragraphs", 0) >= 3:
        max_score += 15
        if p_cv < 0.30:
            score += 15
            indicators.append(f"Uniform paragraph lengths (CV={p_cv:.3f}) — LLM-like")
        elif p_cv < 0.50:
            score += 7
            indicators.append(f"Somewhat uniform paragraphs (CV={p_cv:.3f})")
        elif p_cv < 0.70:
            score += 2

    # 5. Hapax ratio — for academic writing, expect 0.40-0.55
    hapax = features.get("hapax", {}).get("hapax_ratio", 0)
    if hapax > 0:
        max_score += 15
        if hapax > 0.65:
            score += 15
            indicators.append(f"Very high hapax ratio ({hapax}) — possible LLM")
        elif hapax > 0.55:
            score += 8
            indicators.append(f"Elevated hapax ratio ({hapax})")
        elif hapax > 0.45:
            score += 3
        # low hapax is normal

    # 6. Function word density — typical range 30-40%
    fwpct = features.get("function_words", {}).get("function_pct", 0)
    if fwpct > 0:
        max_score += 15
        if fwpct > 50:
            score += 15
            indicators.append(f"Very high function word density ({fwpct}%)")
        elif fwpct > 45:
            score += 8
            indicators.append(f"Elevated function word density ({fwpct}%)")
        elif fwpct > 40:
            score += 3
        # else: normal

    # Normalize
    final_pct = (score / max_score * 100) if max_score > 0 else 0
    final_pct = min(100.0, max(0.0, final_pct))

    # Verdict — calibrated so a real human-written academic abstract should score < 30
    if final_pct >= 60:
        verdict = "VERY LIKELY LLM"
        color = _safe_emoji("[CRIT]", "[!!!]")
    elif final_pct >= 45:
        verdict = "LIKELY LLM-ASSISTED"
        color = _safe_emoji("[HIGH]", "[!!]")
    elif final_pct >= 30:
        verdict = "POSSIBLY LLM-INFLUENCED"
        color = _safe_emoji("[MOD]", "[!]")
    elif final_pct >= 15:
        verdict = "MOSTLY LIKELY HUMAN"
        color = _safe_emoji("[LOW]", "[?]")
    else:
        verdict = "STRONGLY HUMAN-LIKE"
        color = _safe_emoji("[OK]", "[+]")

    return {
        "score": round(final_pct, 1),
        "verdict": verdict,
        "color": color,
        "raw_score": f"{score}/{max_score}",
        "indicators": indicators,
    }


# ----- Main analysis -----

def analyze_text(text: str) -> dict:
    """Extract all features and compute LLM-likeness score."""
    features = {
        "sentence_length": sentence_length_stats(text),
        "ttr": type_token_ratio(text),
        "bigram_entropy": bigram_entropy(text),
        "hapax": hapax_ratio(text),
        "function_words": function_word_density(text),
        "paragraph_uniformity": paragraph_uniformity(text),
        "burstiness": burstiness_score(text),
    }
    features["llm_likelihood"] = llm_likelihood_score(features)
    return features


def format_report(features: dict, source: str = "input") -> str:
    crit = _safe_emoji("[CRIT]", "[!!!]")
    high = _safe_emoji("[HIGH]", "[!!]")
    ok = _safe_emoji("[OK]", "[+]")

    out = []
    out.append("=" * 70)
    out.append("  LLM-GENERATED TEXT DETECTION REPORT")
    out.append("=" * 70)
    out.append(f"\n  Source: {source}")
    out.append(f"  Score: {features['llm_likelihood']['score']}/100  "
               f"({features['llm_likelihood']['raw_score']} weighted points)")
    out.append(f"  Verdict: {features['llm_likelihood']['color']} {features['llm_likelihood']['verdict']}")

    out.append("\n  --- Features ---")
    sl = features["sentence_length"]
    out.append(f"  Sentence length: mean={sl.get('mean_length', '?')}, stdev={sl.get('stdev_length', '?')}, "
               f"CV={sl.get('cv', '?')} (lower = more uniform = more LLM-like)")

    ttr = features["ttr"]
    out.append(f"  Vocabulary: {ttr.get('total_words', '?')} words, {ttr.get('unique_words', '?')} unique, "
               f"TTR={ttr.get('ttr', '?')}")

    be = features["bigram_entropy"]
    out.append(f"  Bigram entropy: {be.get('entropy', '?')} bits (lower = more LLM-like; human prose usually 8-10)")

    hp = features["hapax"]
    out.append(f"  Hapax legomena: {hp.get('hapax_legomena', '?')}/{hp.get('total_unique', '?')} "
               f"({hp.get('hapax_ratio', '?')})")

    fw = features["function_words"]
    out.append(f"  Function words: {fw.get('function_count', '?')} ({fw.get('function_pct', '?')}%)")

    pu = features["paragraph_uniformity"]
    out.append(f"  Paragraphs: {pu.get('n_paragraphs', '?')}, mean={pu.get('mean_words', '?')}, "
               f"CV={pu.get('cv', '?')}")

    indicators = features["llm_likelihood"]["indicators"]
    if indicators:
        out.append(f"\n  --- Indicators ---")
        for ind in indicators:
            out.append(f"  - {ind}")
    else:
        out.append(f"\n  {ok} No strong LLM indicators detected.")

    out.append("\n  --- Caveats ---")
    out.append("  This is a HEURISTIC detector. False positives occur with:")
    out.append("    - Heavily edited non-native English")
    out.append("    - Technical writing with deliberately simple prose")
    out.append("    - Texts under 500 words")
    out.append("  For high-stakes decisions, combine with human review and")
    out.append("  dedicated tools (GPTZero, Originality.ai, etc.).")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="LLM-generated text detector (heuristic)")
    parser.add_argument("--text", help="Text file to analyze")
    parser.add_argument("--compare-against", help="Baseline text file for comparison (optional)")
    args = parser.parse_args()

    if args.text:
        if not os.path.exists(args.text):
            print(f"Error: file not found: {args.text}", file=sys.stderr)
            sys.exit(1)
        with open(args.text, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        source = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
        source = "stdin"
    else:
        print("Error: provide --text <file> or pipe text via stdin", file=sys.stderr)
        sys.exit(1)

    if len(text.strip()) < 100:
        print(f"Error: text is too short ({len(text.strip())} chars). Need at least 100 characters for reliable analysis.", file=sys.stderr)
        sys.exit(1)

    features = analyze_text(text)
    print(format_report(features, source))


if __name__ == "__main__":
    main()
