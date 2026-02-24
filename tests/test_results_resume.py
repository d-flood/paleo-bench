import json
import tempfile
import unittest
from pathlib import Path

from paleo_bench.config import (
    BenchConfig,
    GroupConfig,
    ModelConfig,
    PromptsConfig,
    SampleConfig,
)
from paleo_bench.results import completed_result_keys, recompute_comparisons, write_results
from paleo_bench.runner import BenchmarkResult, SampleResult


def _bench_config() -> BenchConfig:
    sample = SampleConfig(
        image_url="https://example.org/iiif/a/info.json",
        ground_truth=Path("data/grk_byz/GAL2010_40v.txt"),
        label="folio-a",
        cached_image=Path("dummy.jpg"),
    )
    return BenchConfig(
        name="Test",
        output=Path("results.json"),
        max_concurrency=1,
        prompts=PromptsConfig(system="s", user="u"),
        models=[
            ModelConfig(id="provider/model-a", label="model-a"),
        ],
        groups=[GroupConfig(name="g1", samples=[sample])],
    )


class TestResultsResume(unittest.TestCase):
    def test_completed_result_keys_filters_by_model(self) -> None:
        data = {
            "results": [
                {
                    "group": "g1",
                    "label": "folio-a",
                    "image": "https://example.org/iiif/a/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "alpha",
                },
                {
                    "group": "g1",
                    "label": "folio-b",
                    "image": "https://example.org/iiif/b/info.json",
                    "ground_truth_file": "data/grk_byz/GAL587_p66.txt",
                    "model": "model-b",
                    "model_output": "beta",
                },
            ]
        }

        only_a = completed_result_keys(data, model_labels={"model-a"})
        self.assertEqual(len(only_a), 1)
        self.assertEqual(next(iter(only_a))[0], "model-a")

    def test_write_results_merges_and_replaces_duplicate_rows(self) -> None:
        config = _bench_config()
        result = BenchmarkResult(config=config, timestamp="2026-02-24T00:00:00+00:00")
        result.sample_results = [
            SampleResult(
                group_name="g1",
                sample_label="folio-a",
                image_url="https://example.org/iiif/a/info.json",
                ground_truth_path="data/grk_byz/GAL2010_40v.txt",
                ground_truth_text="gt",
                model_id="model-a",
                model_output="new-output",
            )
        ]
        result.model_summaries = {"model-a": {"samples_evaluated": 1}}
        result.group_summaries = {"model-a": {"g1": {"samples_evaluated": 1}}}

        existing_data = {
            "benchmark": {
                "config": {
                    "models": [{"label": "model-b", "id": "provider/model-b", "params": {}}]
                }
            },
            "results": [
                {
                    "group": "g1",
                    "label": "folio-a",
                    "image": "https://example.org/iiif/a/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "old-output",
                },
                {
                    "group": "g1",
                    "label": "folio-b",
                    "image": "https://example.org/iiif/b/info.json",
                    "ground_truth_file": "data/grk_byz/GAL587_p66.txt",
                    "model": "model-b",
                    "model_output": "keep-me",
                },
            ],
            "model_summaries": {"model-b": {"samples_evaluated": 1}},
            "group_summaries": {"model-b": {"g1": {"samples_evaluated": 1}}},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "results.json"
            write_results(result, output_path, existing_data=existing_data)
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(data["results"]), 2)
        rows_by_model = {row["model"]: row for row in data["results"]}
        self.assertEqual(rows_by_model["model-a"]["model_output"], "new-output")
        self.assertEqual(rows_by_model["model-b"]["model_output"], "keep-me")
        self.assertIn("model-a", data["model_summaries"])
        self.assertIn("model-b", data["model_summaries"])

    def test_completed_result_keys_excludes_rows_with_errors_or_missing_output(self) -> None:
        data = {
            "results": [
                {
                    "group": "g1",
                    "label": "ok",
                    "image": "https://example.org/iiif/ok/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "valid transcription",
                    "error": None,
                },
                {
                    "group": "g1",
                    "label": "empty",
                    "image": "https://example.org/iiif/empty/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "",
                    "error": None,
                },
                {
                    "group": "g1",
                    "label": "err-field",
                    "image": "https://example.org/iiif/err-field/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "something",
                    "error": "BadRequestError: boom",
                },
                {
                    "group": "g1",
                    "label": "err-output",
                    "image": "https://example.org/iiif/err-output/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "BadRequestError: AnthropicException - ...",
                    "error": None,
                },
            ]
        }

        keys = completed_result_keys(data, model_labels={"model-a"})
        self.assertEqual(len(keys), 1)
        only = next(iter(keys))
        self.assertEqual(only[3], "ok")

    def test_write_results_recomputes_model_summary_from_merged_rows(self) -> None:
        config = _bench_config()
        result = BenchmarkResult(config=config, timestamp="2026-02-24T00:00:00+00:00")
        result.sample_results = []
        result.model_summaries = {"model-a": {"samples_evaluated": 0, "cer_mean": 0.0}}

        existing_data = {
            "benchmark": {"config": {"models": []}},
            "results": [
                {
                    "group": "g1",
                    "label": "folio-a",
                    "image": "https://example.org/iiif/a/info.json",
                    "ground_truth_file": "data/grk_byz/GAL2010_40v.txt",
                    "model": "model-a",
                    "model_output": "new-output",
                    "error": None,
                    "metrics": {
                        "cer": 0.1,
                        "wer": 0.2,
                        "cer_case_insensitive": 0.1,
                        "wer_case_insensitive": 0.2,
                        "levenshtein_distance": 3,
                        "normalized_levenshtein_similarity": 0.9,
                        "char_count_reference": 10,
                        "word_count_reference": 2,
                    },
                    "response_metadata": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cost": 0.01,
                        "latency_seconds": 1.25,
                    },
                }
            ],
            "model_summaries": {"model-a": {"samples_evaluated": 0, "cer_mean": 0.0}},
            "group_summaries": {},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "results.json"
            write_results(result, output_path, existing_data=existing_data)
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(data["model_summaries"]["model-a"]["samples_evaluated"], 1)
        self.assertEqual(data["model_summaries"]["model-a"]["cer_mean"], 0.1)
        self.assertEqual(data["model_summaries"]["model-a"]["total_tokens"], 120)

    def test_recompute_comparisons_recalculates_metrics_from_ground_truth_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            gt_path = tmp_path / "gt.txt"
            gt_path.write_text("alpha beta", encoding="utf-8")
            data = {
                "benchmark": {
                    "config": {"models": [{"label": "model-a", "id": "provider/model-a", "params": {}}]}
                },
                "results": [
                    {
                        "group": "g1",
                        "label": "folio-a",
                        "image": "https://example.org/iiif/a/info.json",
                        "ground_truth_file": "gt.txt",
                        "model": "model-a",
                        "model_output": "alpha gamma",
                        "error": None,
                        "metrics": None,
                        "response_metadata": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cost": 0.001,
                            "latency_seconds": 0.5,
                        },
                    }
                ],
            }

            recomputed, skipped = recompute_comparisons(data, config_dir=tmp_path)

        self.assertEqual(recomputed, 1)
        self.assertEqual(skipped, 0)
        self.assertIsNotNone(data["results"][0]["metrics"])
        self.assertEqual(data["results"][0]["ground_truth_text"], "alpha beta")
        self.assertEqual(data["results"][0]["metrics"]["levenshtein_distance"], 4)
        self.assertEqual(data["model_summaries"]["model-a"]["samples_evaluated"], 1)
        self.assertIn("g1", data["group_summaries"]["model-a"])

    def test_recompute_comparisons_skips_rows_with_missing_ground_truth(self) -> None:
        data = {
            "benchmark": {
                "config": {"models": [{"label": "model-a", "id": "provider/model-a", "params": {}}]}
            },
            "results": [
                {
                    "group": "g1",
                    "label": "folio-a",
                    "image": "https://example.org/iiif/a/info.json",
                    "ground_truth_file": "missing.txt",
                    "model": "model-a",
                    "model_output": "alpha",
                    "error": None,
                    "metrics": {"cer": 0.0},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            recomputed, skipped = recompute_comparisons(data, config_dir=Path(tmp_dir))

        self.assertEqual(recomputed, 0)
        self.assertEqual(skipped, 1)
        self.assertIsNone(data["results"][0]["metrics"])
        self.assertEqual(data["model_summaries"]["model-a"]["samples_evaluated"], 0)


if __name__ == "__main__":
    unittest.main()
