import tempfile
import unittest
from pathlib import Path

from paleo_bench.config import ConfigError, load_config


def _write_config(tmp: Path, side_line: str | None) -> Path:
    gt = tmp / "gt.txt"
    gt.write_text("alpha", encoding="utf-8")
    config = tmp / "config.toml"
    lines = [
        "[bench]",
        'name = "Test"',
        'output = "results.json"',
        "max_concurrency = 1",
        "",
        "[prompts]",
        'system = "s"',
        'user = "u"',
        "",
        "[[models]]",
        'id = "provider/model-a"',
        'label = "model-a"',
        "",
        "[[groups]]",
        'name = "g1"',
        "",
        "[[groups.samples]]",
        'image = "https://example.org/iiif/a/info.json"',
        'ground_truth = "gt.txt"',
    ]
    if side_line:
        lines.append(side_line)
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config


class TestConfigSide(unittest.TestCase):
    def test_load_config_accepts_side_verso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_config(Path(tmp_dir), 'side = "verso"')
            config = load_config(path)
        self.assertEqual(config.groups[0].samples[0].side, "verso")

    def test_load_config_accepts_side_recto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_config(Path(tmp_dir), 'side = "recto"')
            config = load_config(path)
        self.assertEqual(config.groups[0].samples[0].side, "recto")

    def test_load_config_allows_missing_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_config(Path(tmp_dir), None)
            config = load_config(path)
        self.assertIsNone(config.groups[0].samples[0].side)

    def test_load_config_rejects_invalid_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_config(Path(tmp_dir), 'side = "left"')
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
