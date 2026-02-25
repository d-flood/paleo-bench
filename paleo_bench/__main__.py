from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import ConfigError, load_config
from .iiif import IIIFError, fetch_iiif_image
from .results import (
    completed_result_keys,
    load_results,
    print_summary,
    recompute_comparisons,
    write_results,
    write_results_data,
)
from .runner import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="paleo_bench",
        description="Handwritten text recognition benchmark for LLM vision models",
    )
    parser.add_argument("--config", required=True, help="Path to TOML config file")
    parser.add_argument("--output", help="Override output path from config")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config only, don't run benchmark",
    )
    parser.add_argument(
        "--recompute-comparisons",
        action="store_true",
        help="Recompute metrics/summaries from existing output using current ground-truth files",
    )
    args = parser.parse_args()

    load_dotenv()

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    if args.output:
        config.output = Path(args.output)

    existing_data = None
    try:
        existing_data = load_results(config.output)
    except ValueError as e:
        print(f"Output error: {e}", file=sys.stderr)
        return 1

    sample_count = sum(len(g.samples) for g in config.groups)
    print(
        f"Config OK: {len(config.models)} model(s), "
        f"{len(config.groups)} group(s), {sample_count} sample(s)",
        file=sys.stderr,
    )

    if args.dry_run:
        return 0

    if args.recompute_comparisons:
        if existing_data is None:
            print(
                f"Output error: no existing results found at {config.output}",
                file=sys.stderr,
            )
            return 1
        config_dir = Path(args.config).resolve().parent
        recomputed, skipped = recompute_comparisons(
            existing_data,
            config_dir=config_dir,
            config=config,
        )
        write_results_data(existing_data, config.output)
        print(
            f"Recomputed comparisons for {recomputed} row(s); skipped {skipped} row(s).",
            file=sys.stderr,
        )
        return 0

    # IIIF prep: download and cache images
    cache_dir = Path(args.config).resolve().parent / ".cache"
    unique_samples = {
        (sample.image_url, sample.side)
        for group in config.groups
        for sample in group.samples
    }
    try:
        sample_to_path: dict[tuple[str, str | None], Path] = {}
        for url, side in unique_samples:
            if side:
                print(f"Fetching IIIF image: {url} (side={side})", file=sys.stderr)
            else:
                print(f"Fetching IIIF image: {url}", file=sys.stderr)
            sample_to_path[(url, side)] = fetch_iiif_image(url, cache_dir, side=side)
        for group in config.groups:
            for sample in group.samples:
                sample.cached_image = sample_to_path[(sample.image_url, sample.side)]
    except IIIFError as e:
        print(f"IIIF error: {e}", file=sys.stderr)
        return 1

    model_labels = {model.label for model in config.models}
    skip_keys = (
        completed_result_keys(existing_data, model_labels=model_labels)
        if existing_data
        else set()
    )
    if skip_keys:
        print(
            f"Found {len(skip_keys)} completed sample/model pairs in {config.output}; resuming.",
            file=sys.stderr,
        )

    try:
        result = asyncio.run(
            run_benchmark(
                config,
                skip_keys=skip_keys,
                on_result=lambda partial: write_results(
                    partial,
                    config.output,
                    existing_data=existing_data,
                ),
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        return 2

    if not result.sample_results:
        print("Nothing to run: all configured sample/model pairs are already complete.", file=sys.stderr)
        return 0

    write_results(result, config.output, existing_data=existing_data)
    print_summary(result)
    return 0


sys.exit(main())
