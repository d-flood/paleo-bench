import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from paleo_bench.config import ConfigError, ModelConfig, PipelineConfig, PromptsConfig, load_config
from paleo_bench.pipeline import Correction, Corrections, call_vote_pipeline, merge, vote, word_ids


def _c(id: str, text: str) -> Correction:
    return Correction(id=id, text=text, change="")


class TestWordIds(unittest.TestCase):
    def test_numbers_text_lines_and_skips_labels_and_blanks(self) -> None:
        text = "Column 1\n\nτιμη αλληλους\nτω\n\nColumn 2\n\nκαι"
        self.assertEqual(
            word_ids(text),
            {"L1.1": "τιμη", "L1.2": "αλληλους", "L2.1": "τω", "L3.1": "και"},
        )


class TestMerge(unittest.TestCase):
    def test_replaces_deletes_and_splits_words(self) -> None:
        text = "Column 1\n\nτιμη αλληλους\nτω εκ"
        merged = merge(text, {"L1.1": "τημη", "L2.2": "", "L1.2": "τα ελεη"})
        self.assertEqual(merged, "Column 1\n\nτημη τα ελεη\nτω")

    def test_ignores_unknown_ids(self) -> None:
        self.assertEqual(merge("τω", {"L9.9": "το"}), "τω")


class TestVote(unittest.TestCase):
    def test_keeps_corrections_with_enough_votes(self) -> None:
        checks = [
            [_c("L1.1", "τημη"), _c("L2.1", "το")],
            [_c("L1.1", "τημη")],
            [_c("L2.1", "τοι")],
        ]
        self.assertEqual(vote(checks, 2), {"L1.1": "τημη"})

    def test_counts_spelling_variants_of_the_same_reading_together(self) -> None:
        checks = [[_c("L1.1", "ὑμᾶς")], [_c("L1.1", "υμας")], [_c("L1.1", "ΥΜΑΣ")]]
        self.assertEqual(vote(checks, 3), {"L1.1": "ὑμᾶς"})

    def test_counts_one_vote_per_check(self) -> None:
        checks = [[_c("L1.1", "τημη"), _c("L1.1", "τημη")], []]
        self.assertEqual(vote(checks, 2), {})


class FakeAgent:
    calls = []
    corrections = []

    def __init__(self, model_id, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def run(self, prompt, **kwargs):
        FakeAgent.calls.append({"agent_kwargs": self.kwargs, "prompt": prompt, **kwargs})
        usage = types.SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)
        response = types.SimpleNamespace(cost=lambda: types.SimpleNamespace(total_price=0.01))
        if self.kwargs["output_type"] is str:
            output = "Column 1\n\nτιμη αλληλους\nτω"
        else:
            output = Corrections(corrections=FakeAgent.corrections.pop(0))
        return types.SimpleNamespace(output=output, usage=usage, response=response)


class TestCallVotePipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.image_path = Path(self.tmp.name) / "sample.png"
        Image.new("RGB", (8, 8), "white").save(self.image_path, format="PNG")
        self.model = ModelConfig(
            id="provider/model-a",
            label="pipeline",
            params={"thinking": "low", "pipeline": {"checks": 3, "votes": 2, "check_thinking": "medium"}},
        )
        self.pipeline = PipelineConfig(
            continuous_notes="continuous", lectionary_notes="lectionary", check_system="check", check_user="Draft:\n"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    async def test_continuous_samples_get_continuous_notes(self) -> None:
        FakeAgent.calls = []
        FakeAgent.corrections = [[], [], []]
        with patch("paleo_bench.vision.Agent", FakeAgent):
            await call_vote_pipeline(
                self.model, self.image_path, PromptsConfig(system="system", user="user"), self.pipeline, False
            )
        self.assertEqual(FakeAgent.calls[0]["agent_kwargs"]["system_prompt"], "system\ncontinuous")

    async def test_merges_agreed_corrections_and_sums_usage(self) -> None:
        FakeAgent.calls = []
        FakeAgent.corrections = [
            [_c("L1.1", "τημη"), _c("L2.1", "το")],
            [_c("L1.1", "τημη")],
            [],
        ]
        with patch("paleo_bench.vision.Agent", FakeAgent):
            response = await call_vote_pipeline(
                self.model, self.image_path, PromptsConfig(system="system", user="user"), self.pipeline, True
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "Column 1\n\nτημη αλληλους\nτω")
        self.assertEqual((response.input_tokens, response.output_tokens), (40, 20))
        self.assertAlmostEqual(response.cost, 0.04)
        draft, *checks = FakeAgent.calls
        self.assertEqual(draft["agent_kwargs"]["system_prompt"], "system\nlectionary")
        self.assertEqual(draft["model_settings"]["thinking"], "low")
        self.assertEqual(len(checks), 3)
        for check in checks:
            self.assertEqual(check["model_settings"]["thinking"], "medium")
            self.assertIn('"L1.1": "τιμη"', check["prompt"][0])


def _write_config(tmp: Path, pipeline: bool, spec: str) -> Path:
    (tmp / "gt.txt").write_text("alpha", encoding="utf-8")
    lines = [
        "[bench]",
        'name = "Test"',
        "",
        "[prompts]",
        'system = "s"',
        'user = "u"',
        "",
    ]
    if pipeline:
        lines += ["[pipeline]", 'continuous_notes = "n"', 'lectionary_notes = "l"', 'check_system = "c"', 'check_user = "u"', ""]
    lines += [
        "[[models]]",
        'id = "provider/model-a"',
        'label = "model-a"',
        f"pipeline = {spec}",
        "",
        "[[groups]]",
        'name = "g1"',
        "",
        "[[groups.samples]]",
        'image = "https://example.org/iiif/a/info.json"',
        'ground_truth = "gt.txt"',
    ]
    path = tmp / "config.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestPipelineConfig(unittest.TestCase):
    def test_loads_pipeline_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(_write_config(Path(tmp), True, "{ checks = 3, votes = 2 }"))
        self.assertEqual(config.pipeline, PipelineConfig("n", "l", "c", "u"))

    def test_rejects_pipeline_model_without_pipeline_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ConfigError, r"\[pipeline\] is missing"):
                load_config(_write_config(Path(tmp), False, "{ checks = 3, votes = 2 }"))

    def test_rejects_more_votes_than_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ConfigError, "votes <= checks"):
                load_config(_write_config(Path(tmp), True, "{ checks = 2, votes = 3 }"))

    def test_model_flag_rejects_unknown_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_config(Path(tmp), True, "{ checks = 3, votes = 2 }")
            proc = subprocess.run(
                [sys.executable, "-m", "paleo_bench", "--config", str(path), "--model", "nope", "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown model label(s): nope", proc.stderr)


if __name__ == "__main__":
    unittest.main()
