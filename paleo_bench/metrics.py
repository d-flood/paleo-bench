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
    cer_case_insensitive: float
    wer_case_insensitive: float
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


def compute_metrics(ground_truth: str, prediction: str) -> MetricScores:
    gt = normalize_for_comparison(ground_truth)
    pred = normalize_for_comparison(prediction)

    gt_lower = gt.lower()
    pred_lower = pred.lower()

    # Handle empty ground truth
    if not gt:
        return MetricScores(
            cer=0.0 if not pred else 1.0,
            wer=0.0 if not pred else 1.0,
            cer_case_insensitive=0.0 if not pred else 1.0,
            wer_case_insensitive=0.0 if not pred else 1.0,
            levenshtein_distance=len(pred),
            normalized_levenshtein_similarity=1.0 if not pred else 0.0,
            char_count_reference=0,
            word_count_reference=0,
        )

    cer = jiwer.cer(gt, pred)
    wer = jiwer.wer(gt, pred)
    cer_ci = jiwer.cer(gt_lower, pred_lower)
    wer_ci = jiwer.wer(gt_lower, pred_lower)

    lev_dist = Levenshtein.distance(gt, pred)
    lev_sim = Levenshtein.normalized_similarity(gt, pred)

    return MetricScores(
        cer=cer,
        wer=wer,
        cer_case_insensitive=cer_ci,
        wer_case_insensitive=wer_ci,
        levenshtein_distance=lev_dist,
        normalized_levenshtein_similarity=lev_sim,
        char_count_reference=len(gt),
        word_count_reference=len(gt.split()),
    )


def aggregate_metrics(scores: list[MetricScores]) -> dict:
    if not scores:
        return {}

    float_fields = [
        "cer", "wer", "cer_case_insensitive", "wer_case_insensitive",
        "normalized_levenshtein_similarity",
    ]
    int_fields = ["levenshtein_distance"]

    result = {}
    for field_name in float_fields + int_fields:
        values = [getattr(s, field_name) for s in scores]
        result[f"{field_name}_mean"] = statistics.mean(values)
        result[f"{field_name}_median"] = statistics.median(values)
        result[f"{field_name}_min"] = min(values)
        result[f"{field_name}_max"] = max(values)

    return result
