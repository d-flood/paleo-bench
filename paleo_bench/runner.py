import asyncio
import inspect
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .config import BenchConfig
from .metrics import (
    MetricScores,
    aggregate_metrics,
    compute_metrics,
    normalize_for_comparison,
)
from .vision import call_vision_model


@dataclass
class SampleResult:
    group_name: str
    sample_label: str
    image_url: str
    ground_truth_path: str
    ground_truth_text: str
    model_id: str
    model_output: str = ""
    error: str | None = None
    metrics: MetricScores | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    latency_seconds: float = 0.0


@dataclass
class BenchmarkResult:
    config: BenchConfig
    sample_results: list[SampleResult] = field(default_factory=list)
    model_summaries: dict = field(default_factory=dict)
    group_summaries: dict = field(default_factory=dict)
    timestamp: str = ""
    total_duration_seconds: float = 0.0


ResultKey = tuple[str, str, str, str, str]


def make_result_key(
    *,
    group_name: str,
    sample_label: str,
    image_url: str,
    ground_truth_path: str,
    model_id: str,
) -> ResultKey:
    return (
        str(model_id),
        str(group_name),
        str(image_url),
        str(sample_label or ""),
        str(ground_truth_path),
    )


def sample_result_key(sample_result: SampleResult) -> ResultKey:
    return make_result_key(
        group_name=sample_result.group_name,
        sample_label=sample_result.sample_label,
        image_url=sample_result.image_url,
        ground_truth_path=sample_result.ground_truth_path,
        model_id=sample_result.model_id,
    )


def recompute_summaries(result: BenchmarkResult) -> None:
    result.model_summaries = {}
    result.group_summaries = {}

    # Compute model summaries
    for model in result.config.models:
        model_results = [
            r for r in result.sample_results if r.model_id == model.label
        ]
        model_scores = [r.metrics for r in model_results if r.metrics is not None]
        failed = sum(1 for r in model_results if r.error is not None)
        summary = aggregate_metrics(model_scores)
        summary["samples_evaluated"] = len(model_scores)
        summary["samples_failed"] = failed
        summary["total_input_tokens"] = sum(r.input_tokens for r in model_results)
        summary["total_output_tokens"] = sum(r.output_tokens for r in model_results)
        summary["total_tokens"] = sum(r.total_tokens for r in model_results)
        summary["total_cost"] = round(sum(r.cost for r in model_results), 6)
        summary["total_latency_seconds"] = round(
            sum(r.latency_seconds for r in model_results), 3
        )
        result.model_summaries[model.label] = summary

    # Compute group summaries: model -> group -> aggregate
    for model in result.config.models:
        result.group_summaries[model.label] = {}
        for group in result.config.groups:
            group_results = [
                r for r in result.sample_results
                if r.model_id == model.label and r.group_name == group.name
            ]
            group_scores = [r.metrics for r in group_results if r.metrics is not None]
            if group_scores:
                agg = aggregate_metrics(group_scores)
                agg["total_input_tokens"] = sum(r.input_tokens for r in group_results)
                agg["total_output_tokens"] = sum(r.output_tokens for r in group_results)
                agg["total_tokens"] = sum(r.total_tokens for r in group_results)
                agg["total_cost"] = round(sum(r.cost for r in group_results), 6)
                agg["total_latency_seconds"] = round(
                    sum(r.latency_seconds for r in group_results), 3
                )
                result.group_summaries[model.label][group.name] = agg


async def run_benchmark(
    config: BenchConfig,
    *,
    skip_keys: set[ResultKey] | None = None,
    on_result: Callable[[BenchmarkResult], Awaitable[None] | None] | None = None,
) -> BenchmarkResult:
    result = BenchmarkResult(
        config=config,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    skipped = skip_keys or set()

    # Build task list: (group, sample, model)
    tasks = []
    for group in config.groups:
        for sample in group.samples:
            gt_text = normalize_for_comparison(
                sample.ground_truth.read_text(encoding="utf-8")
            )
            for model in config.models:
                key = make_result_key(
                    group_name=group.name,
                    sample_label=sample.label,
                    image_url=sample.image_url,
                    ground_truth_path=str(sample.ground_truth),
                    model_id=model.label,
                )
                if key in skipped:
                    continue
                tasks.append((group, sample, model, gt_text))

    total = len(tasks)
    if total == 0:
        return result

    semaphore = asyncio.Semaphore(config.max_concurrency)
    started = 0
    completed = 0
    lock = asyncio.Lock()

    async def process(group, sample, model, gt_text):
        nonlocal started, completed
        async with lock:
            started += 1
            n = started
        # Use sample label if provided, otherwise extract identifier from URL
        label = sample.label or sample.image_url.rsplit("/info.json", 1)[0].rsplit("/", 1)[-1]
        print(
            f"[{n}/{total}] Evaluating {label} with {model.label}...",
            file=sys.stderr,
        )

        async with semaphore:
            response = await call_vision_model(model, sample.cached_image, config.prompts)

        async with lock:
            completed += 1
            done = completed
        status = "ok" if not response.error else "FAIL"
        print(
            f"  [{done}/{total} done] {label} × {model.label} — {status} ({response.latency_seconds}s)",
            file=sys.stderr,
        )

        sr = SampleResult(
            group_name=group.name,
            sample_label=sample.label,
            image_url=sample.image_url,
            ground_truth_path=str(sample.ground_truth),
            ground_truth_text=gt_text,
            model_id=model.label,
            model_output=normalize_for_comparison(response.text),
            error=response.error,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            cost=response.cost,
            latency_seconds=response.latency_seconds,
        )

        if not response.error:
            sr.metrics = compute_metrics(gt_text, response.text)

        return sr

    start = time.monotonic()
    futures = [asyncio.create_task(process(g, s, m, gt)) for g, s, m, gt in tasks]
    for future in asyncio.as_completed(futures):
        sample_result = await future
        result.sample_results.append(sample_result)
        recompute_summaries(result)
        if on_result:
            callback_result = on_result(result)
            if inspect.isawaitable(callback_result):
                await callback_result
    result.total_duration_seconds = round(time.monotonic() - start, 3)

    recompute_summaries(result)

    return result
