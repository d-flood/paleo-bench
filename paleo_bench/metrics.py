from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass

import jiwer
from rapidfuzz.distance import Levenshtein


@dataclass
class MetricScores:
    cer: float
    wer: float
    levenshtein_distance: int
    normalized_levenshtein_similarity: float
    char_count_reference: int
    word_count_reference: int


def normalize_for_comparison(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    no_diacritics = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    no_punctuation = "".join(
        ch for ch in no_diacritics if not unicodedata.category(ch).startswith("P")
    )
    normalized_whitespace = re.sub(r"[^\S\r\n]+", " ", no_punctuation)
    # Ignore trailing spaces/tabs (including line ends), but keep newlines significant.
    without_trailing_whitespace = re.sub(r"[ \t]+(?=\r?\n|$)", "", normalized_whitespace)
    return unicodedata.normalize("NFC", without_trailing_whitespace)


_GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_LOOKALIKES = str.maketrans(
    {
        "A": "Α", "B": "Β", "C": "Ϲ", "E": "Ε", "H": "Η", "I": "Ι", "K": "Κ", "M": "Μ",
        "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ", "Y": "Υ", "Z": "Ζ",
        "a": "α", "c": "ϲ", "i": "ι", "k": "κ", "o": "ο", "p": "ρ", "u": "υ", "v": "ν", "x": "χ",
        "А": "Α", "В": "Β", "Г": "Γ", "Е": "Ε", "К": "Κ", "Л": "Λ", "М": "Μ", "Н": "Η",
        "О": "Ο", "П": "Π", "Р": "Ρ", "С": "Ϲ", "Т": "Τ", "Ф": "Φ", "Х": "Χ",
        "а": "α", "к": "κ", "о": "ο", "п": "π", "р": "ρ", "с": "ϲ", "т": "τ", "ф": "φ", "х": "χ",
    }
)
_LETTER_FORMS = str.maketrans({"ς": "σ", "ϛ": "στ", "ȣ": "ου", "ϗ": "και"})


def _greek_lookalikes(match: re.Match[str]) -> str:
    word = match.group()
    return word.translate(_LOOKALIKES) if _GREEK.search(word) else word


def regularize_for_scoring(text: str) -> str:
    text = re.sub(r"\S+", _greek_lookalikes, text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Sk", "Lm"))
    text = unicodedata.normalize("NFKD", text)
    text = unicodedata.normalize("NFC", "".join(ch for ch in text if unicodedata.category(ch) != "Mn"))
    return text.lower().translate(_LETTER_FORMS)


def compute_metrics(ground_truth: str, prediction: str) -> MetricScores:
    gt = regularize_for_scoring(normalize_for_comparison(ground_truth))
    pred = regularize_for_scoring(normalize_for_comparison(prediction))

    # Handle empty ground truth
    if not gt:
        return MetricScores(
            cer=0.0 if not pred else 1.0,
            wer=0.0 if not pred else 1.0,
            levenshtein_distance=len(pred),
            normalized_levenshtein_similarity=1.0 if not pred else 0.0,
            char_count_reference=0,
            word_count_reference=0,
        )

    cer = jiwer.cer(gt, pred)
    wer = jiwer.wer(gt, pred)

    lev_dist = Levenshtein.distance(gt, pred)
    lev_sim = Levenshtein.normalized_similarity(gt, pred)

    return MetricScores(
        cer=cer,
        wer=wer,
        levenshtein_distance=lev_dist,
        normalized_levenshtein_similarity=lev_sim,
        char_count_reference=len(gt),
        word_count_reference=len(gt.split()),
    )


def aggregate_metrics(scores: list[MetricScores]) -> dict:
    if not scores:
        return {}

    float_fields = ["cer", "wer", "normalized_levenshtein_similarity"]
    int_fields = ["levenshtein_distance"]

    result = {}
    for field_name in float_fields + int_fields:
        values = [getattr(s, field_name) for s in scores]
        result[f"{field_name}_mean"] = statistics.mean(values)
        result[f"{field_name}_median"] = statistics.median(values)
        result[f"{field_name}_min"] = min(values)
        result[f"{field_name}_max"] = max(values)

    return result
