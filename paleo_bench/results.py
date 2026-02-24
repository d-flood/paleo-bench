from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .metrics import MetricScores, aggregate_metrics, compute_metrics, normalize_for_comparison
from .runner import BenchmarkResult, ResultKey, make_result_key


def _build_json(result: BenchmarkResult) -> dict:
    config = result.config
    sample_count = sum(len(g.samples) for g in config.groups)

    output = {
        "benchmark": {
            "name": config.name,
            "timestamp": result.timestamp,
            "total_duration_seconds": result.total_duration_seconds,
            "config": {
                "prompts": {
                    "system": config.prompts.system,
                    "user": config.prompts.user,
                },
                "models": [
                    {"label": m.label, "id": m.id, "params": m.params}
                    for m in config.models
                ],
                "groups": [
                    {
                        "name": g.name,
                        "sample_count": len(g.samples),
                    }
                    for g in config.groups
                ],
                "sample_count": sample_count,
            },
        },
        "results": [],
        "model_summaries": result.model_summaries,
        "group_summaries": result.group_summaries,
    }

    for sr in result.sample_results:
        entry = {
            "group": sr.group_name,
            "label": sr.sample_label,
            "image": sr.image_url,
            "ground_truth_file": sr.ground_truth_path,
            "ground_truth_text": sr.ground_truth_text,
            "model": sr.model_id,
            "model_output": sr.model_output,
            "error": sr.error,
            "metrics": asdict(sr.metrics) if sr.metrics else None,
            "response_metadata": {
                "input_tokens": sr.input_tokens,
                "output_tokens": sr.output_tokens,
                "cost": sr.cost,
                "latency_seconds": sr.latency_seconds,
            },
        }
        output["results"].append(entry)

    return output


def load_results(output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists():
        return None

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Output file is not valid JSON: {output_path} ({e})") from e


def _row_key(row: dict[str, Any]) -> ResultKey | None:
    model_id = row.get("model")
    group_name = row.get("group")
    image_url = row.get("image")
    ground_truth_path = row.get("ground_truth_file")

    if not model_id or not group_name or not image_url or not ground_truth_path:
        return None

    return make_result_key(
        model_id=str(model_id),
        group_name=str(group_name),
        image_url=str(image_url),
        sample_label=str(row.get("label") or ""),
        ground_truth_path=str(ground_truth_path),
    )


def _looks_like_error_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if not text:
        return False
    markers = (
        "error:",
        "badrequesterror",
        "anthropicexception",
        "rate limit",
        "timeout",
        "traceback",
    )
    return any(marker in text for marker in markers)


def _is_completed_row(row: dict[str, Any]) -> bool:
    error = row.get("error")
    if isinstance(error, str) and error.strip():
        return False

    output = row.get("model_output")
    if not isinstance(output, str) or not output.strip():
        return False

    if _looks_like_error_text(output):
        return False

    return True


def _metric_scores_from_row(row: dict[str, Any]) -> MetricScores | None:
    metrics = row.get("metrics")
    if not isinstance(metrics, dict):
        return None
    try:
        return MetricScores(
            cer=float(metrics["cer"]),
            wer=float(metrics["wer"]),
            cer_case_insensitive=float(metrics["cer_case_insensitive"]),
            wer_case_insensitive=float(metrics["wer_case_insensitive"]),
            levenshtein_distance=int(metrics["levenshtein_distance"]),
            normalized_levenshtein_similarity=float(
                metrics["normalized_levenshtein_similarity"]
            ),
            char_count_reference=int(metrics["char_count_reference"]),
            word_count_reference=int(metrics["word_count_reference"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _recompute_model_summaries(
    data: dict[str, Any],
    *,
    model_labels: set[str],
) -> dict[str, dict[str, Any]]:
    scores_by_model: dict[str, list[MetricScores]] = {label: [] for label in model_labels}
    failed_by_model: dict[str, int] = {label: 0 for label in model_labels}
    input_tokens_by_model: dict[str, int] = {label: 0 for label in model_labels}
    output_tokens_by_model: dict[str, int] = {label: 0 for label in model_labels}
    total_tokens_by_model: dict[str, int] = {label: 0 for label in model_labels}
    cost_by_model: dict[str, float] = {label: 0.0 for label in model_labels}
    latency_by_model: dict[str, float] = {label: 0.0 for label in model_labels}

    for row in data.get("results", []):
        model_id = row.get("model")
        if not isinstance(model_id, str):
            continue
        if model_id not in scores_by_model:
            scores_by_model[model_id] = []
            failed_by_model[model_id] = 0
            input_tokens_by_model[model_id] = 0
            output_tokens_by_model[model_id] = 0
            total_tokens_by_model[model_id] = 0
            cost_by_model[model_id] = 0.0
            latency_by_model[model_id] = 0.0

        error = row.get("error")
        if isinstance(error, str) and error.strip():
            failed_by_model[model_id] += 1

        metrics = _metric_scores_from_row(row)
        if metrics is not None:
            scores_by_model[model_id].append(metrics)

        response_metadata = row.get("response_metadata")
        if isinstance(response_metadata, dict):
            input_tokens_by_model[model_id] += int(response_metadata.get("input_tokens", 0) or 0)
            output_tokens_by_model[model_id] += int(
                response_metadata.get("output_tokens", 0) or 0
            )
            total_tokens_by_model[model_id] += (
                int(response_metadata.get("input_tokens", 0) or 0)
                + int(response_metadata.get("output_tokens", 0) or 0)
            )
            cost_by_model[model_id] += float(response_metadata.get("cost", 0.0) or 0.0)
            latency_by_model[model_id] += float(
                response_metadata.get("latency_seconds", 0.0) or 0.0
            )

    summaries: dict[str, dict[str, Any]] = {}
    for model_id in scores_by_model:
        summary = aggregate_metrics(scores_by_model[model_id])
        summary["samples_evaluated"] = len(scores_by_model[model_id])
        summary["samples_failed"] = failed_by_model[model_id]
        summary["total_input_tokens"] = input_tokens_by_model[model_id]
        summary["total_output_tokens"] = output_tokens_by_model[model_id]
        summary["total_tokens"] = total_tokens_by_model[model_id]
        summary["total_cost"] = round(cost_by_model[model_id], 6)
        summary["total_latency_seconds"] = round(latency_by_model[model_id], 3)
        summaries[model_id] = summary
    return summaries


def _recompute_group_summaries(data: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    scores_by_model_group: dict[str, dict[str, list[MetricScores]]] = {}
    input_tokens_by_model_group: dict[str, dict[str, int]] = {}
    output_tokens_by_model_group: dict[str, dict[str, int]] = {}
    total_tokens_by_model_group: dict[str, dict[str, int]] = {}
    cost_by_model_group: dict[str, dict[str, float]] = {}
    latency_by_model_group: dict[str, dict[str, float]] = {}

    for row in data.get("results", []):
        model_id = row.get("model")
        group_name = row.get("group")
        if not isinstance(model_id, str) or not isinstance(group_name, str):
            continue

        scores_by_model_group.setdefault(model_id, {}).setdefault(group_name, [])
        input_tokens_by_model_group.setdefault(model_id, {}).setdefault(group_name, 0)
        output_tokens_by_model_group.setdefault(model_id, {}).setdefault(group_name, 0)
        total_tokens_by_model_group.setdefault(model_id, {}).setdefault(group_name, 0)
        cost_by_model_group.setdefault(model_id, {}).setdefault(group_name, 0.0)
        latency_by_model_group.setdefault(model_id, {}).setdefault(group_name, 0.0)

        metrics = _metric_scores_from_row(row)
        if metrics is not None:
            scores_by_model_group[model_id][group_name].append(metrics)

        response_metadata = row.get("response_metadata")
        if isinstance(response_metadata, dict):
            input_tokens = int(response_metadata.get("input_tokens", 0) or 0)
            output_tokens = int(response_metadata.get("output_tokens", 0) or 0)
            input_tokens_by_model_group[model_id][group_name] += input_tokens
            output_tokens_by_model_group[model_id][group_name] += output_tokens
            total_tokens_by_model_group[model_id][group_name] += input_tokens + output_tokens
            cost_by_model_group[model_id][group_name] += float(response_metadata.get("cost", 0.0) or 0.0)
            latency_by_model_group[model_id][group_name] += float(
                response_metadata.get("latency_seconds", 0.0) or 0.0
            )

    summaries: dict[str, dict[str, dict[str, Any]]] = {}
    for model_id, groups in scores_by_model_group.items():
        summaries[model_id] = {}
        for group_name, scores in groups.items():
            if not scores:
                continue
            agg = aggregate_metrics(scores)
            agg["total_input_tokens"] = input_tokens_by_model_group[model_id][group_name]
            agg["total_output_tokens"] = output_tokens_by_model_group[model_id][group_name]
            agg["total_tokens"] = total_tokens_by_model_group[model_id][group_name]
            agg["total_cost"] = round(cost_by_model_group[model_id][group_name], 6)
            agg["total_latency_seconds"] = round(latency_by_model_group[model_id][group_name], 3)
            summaries[model_id][group_name] = agg
    return summaries


def completed_result_keys(
    data: dict[str, Any],
    *,
    model_labels: set[str] | None = None,
) -> set[ResultKey]:
    keys: set[ResultKey] = set()
    for row in data.get("results", []):
        key = _row_key(row)
        if not key:
            continue
        if model_labels and key[0] not in model_labels:
            continue
        if not _is_completed_row(row):
            continue
        keys.add(key)
    return keys


def recompute_comparisons(
    data: dict[str, Any],
    *,
    config_dir: Path,
) -> tuple[int, int]:
    recomputed_rows = 0
    skipped_rows = 0

    for row in data.get("results", []):
        error = row.get("error")
        output = row.get("model_output")
        gt_path_value = row.get("ground_truth_file")
        if isinstance(error, str) and error.strip():
            row["metrics"] = None
            skipped_rows += 1
            continue
        if not isinstance(output, str) or not output.strip():
            row["metrics"] = None
            skipped_rows += 1
            continue
        if not isinstance(gt_path_value, str) or not gt_path_value.strip():
            row["metrics"] = None
            skipped_rows += 1
            continue

        gt_path = Path(gt_path_value)
        if not gt_path.is_absolute():
            gt_path = config_dir / gt_path
        if not gt_path.exists():
            row["metrics"] = None
            skipped_rows += 1
            continue

        ground_truth_text = gt_path.read_text(encoding="utf-8")
        row["ground_truth_text"] = normalize_for_comparison(ground_truth_text)
        row["metrics"] = asdict(compute_metrics(ground_truth_text, output))
        recomputed_rows += 1

    model_labels = {
        str(model.get("label"))
        for model in data.get("benchmark", {}).get("config", {}).get("models", [])
        if model.get("label")
    }
    for row in data.get("results", []):
        model_id = row.get("model")
        if isinstance(model_id, str) and model_id:
            model_labels.add(model_id)

    data["model_summaries"] = _recompute_model_summaries(data, model_labels=model_labels)
    data["group_summaries"] = _recompute_group_summaries(data)
    return recomputed_rows, skipped_rows


def _merge_existing_results(new_data: dict[str, Any], existing_data: dict[str, Any]) -> None:
    merged_rows: dict[ResultKey, dict[str, Any]] = {}
    passthrough_rows: list[dict[str, Any]] = []

    for row in existing_data.get("results", []):
        key = _row_key(row)
        if key is None:
            passthrough_rows.append(row)
            continue
        merged_rows[key] = row

    for row in new_data.get("results", []):
        key = _row_key(row)
        if key is None:
            passthrough_rows.append(row)
            continue
        merged_rows[key] = row

    new_data["results"] = passthrough_rows + list(merged_rows.values())

    combined_group_summaries = dict(existing_data.get("group_summaries", {}))
    combined_group_summaries.update(new_data.get("group_summaries", {}))
    new_data["group_summaries"] = combined_group_summaries

    model_configs = new_data.get("benchmark", {}).get("config", {}).get("models", [])
    known_labels = {m.get("label") for m in model_configs}
    for model in existing_data.get("benchmark", {}).get("config", {}).get("models", []):
        label = model.get("label")
        if label and label not in known_labels:
            model_configs.append(model)
            known_labels.add(label)

    new_data["model_summaries"] = _recompute_model_summaries(
        new_data,
        model_labels={str(label) for label in known_labels if label},
    )


def write_results(
    result: BenchmarkResult,
    output_path: Path,
    existing_data: dict[str, Any] | None = None,
) -> None:
    data = _build_json(result)
    if existing_data:
        _merge_existing_results(data, existing_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, output_path)
    print(f"\nResults written to {output_path}", file=sys.stderr)


def write_results_data(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, output_path)
    print(f"\nResults written to {output_path}", file=sys.stderr)


def _fmt_cost(cost: float) -> str:
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def print_summary(result: BenchmarkResult) -> None:
    # Overall model summary table
    print("\n=== Model Summary ===", file=sys.stderr)
    header = (
        f"{'Model':<40} {'CER(avg)':>9} {'WER(avg)':>9}"
        f" {'Tokens':>9} {'Cost':>9} {'Time(s)':>8}"
        f" {'Samples':>8} {'Errors':>7}"
    )
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)

    for model_id, summary in result.model_summaries.items():
        cer = summary.get("cer_mean", 0)
        wer = summary.get("wer_mean", 0)
        tokens = summary.get("total_tokens", 0)
        cost = summary.get("total_cost", 0)
        latency = summary.get("total_latency_seconds", 0)
        evaluated = summary.get("samples_evaluated", 0)
        failed = summary.get("samples_failed", 0)
        print(
            f"{model_id:<40} {cer:>9.4f} {wer:>9.4f}"
            f" {tokens:>9} {_fmt_cost(cost):>9} {latency:>8.1f}"
            f" {evaluated:>8} {failed:>7}",
            file=sys.stderr,
        )

    # Per-group breakdown
    if result.group_summaries:
        print("\n=== Per-Group Breakdown ===", file=sys.stderr)
        header = (
            f"{'Model':<40} {'Group':<20} {'CER(avg)':>9} {'WER(avg)':>9}"
            f" {'Tokens':>9} {'Cost':>9} {'Time(s)':>8}"
        )
        print(header, file=sys.stderr)
        print("-" * len(header), file=sys.stderr)

        for model_id, groups in result.group_summaries.items():
            for group_name, agg in groups.items():
                cer = agg.get("cer_mean", 0)
                wer = agg.get("wer_mean", 0)
                tokens = agg.get("total_tokens", 0)
                cost = agg.get("total_cost", 0)
                latency = agg.get("total_latency_seconds", 0)
                print(
                    f"{model_id:<40} {group_name:<20} {cer:>9.4f} {wer:>9.4f}"
                    f" {tokens:>9} {_fmt_cost(cost):>9} {latency:>8.1f}",
                    file=sys.stderr,
                )

    print(
        f"\nTotal duration: {result.total_duration_seconds:.1f}s",
        file=sys.stderr,
    )
