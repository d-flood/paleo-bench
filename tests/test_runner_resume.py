import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paleo_bench.config import (
    BenchConfig,
    GroupConfig,
    ModelConfig,
    PromptsConfig,
    SampleConfig,
)
from paleo_bench.runner import make_result_key, run_benchmark
from paleo_bench.vision import VisionResponse


def _build_config(tmp_dir: Path) -> BenchConfig:
    gt1 = tmp_dir / "gt1.txt"
    gt2 = tmp_dir / "gt2.txt"
    gt1.write_text("alpha", encoding="utf-8")
    gt2.write_text("beta", encoding="utf-8")
    image = tmp_dir / "dummy.jpg"
    image.write_bytes(b"dummy")

    samples = [
        SampleConfig(
            image_url="https://example.org/iiif/a/info.json",
            ground_truth=gt1,
            label="a",
            cached_image=image,
        ),
        SampleConfig(
            image_url="https://example.org/iiif/b/info.json",
            ground_truth=gt2,
            label="b",
            cached_image=image,
        ),
    ]
    return BenchConfig(
        name="Test",
        output=tmp_dir / "results.json",
        max_concurrency=2,
        prompts=PromptsConfig(system="s", user="u"),
        models=[ModelConfig(id="provider/model", label="model-a")],
        groups=[GroupConfig(name="g1", samples=samples)],
    )


class TestRunnerResume(unittest.TestCase):
    def test_run_benchmark_skips_existing_pairs_and_calls_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = _build_config(Path(tmp_dir))
            skip = {
                make_result_key(
                    model_id="model-a",
                    group_name="g1",
                    image_url="https://example.org/iiif/a/info.json",
                    sample_label="a",
                    ground_truth_path=str(config.groups[0].samples[0].ground_truth),
                )
            }
            checkpoints: list[int] = []

            async def fake_call_vision_model(*_args, **_kwargs) -> VisionResponse:
                return VisionResponse(text="ok", latency_seconds=0.01)

            def on_result(partial_result) -> None:
                checkpoints.append(len(partial_result.sample_results))

            with patch("paleo_bench.runner.call_vision_model", new=fake_call_vision_model):
                result = asyncio.run(
                    run_benchmark(
                        config,
                        skip_keys=skip,
                        on_result=on_result,
                    )
                )

        self.assertEqual(len(result.sample_results), 1)
        self.assertEqual(checkpoints, [1])
        self.assertEqual(result.sample_results[0].sample_label, "b")


if __name__ == "__main__":
    unittest.main()
