import subprocess
import sys
import unittest


class TestCliFlags(unittest.TestCase):
    def test_skip_existing_models_flag_is_removed(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "paleo_bench",
                "--config",
                "does-not-matter.toml",
                "--skip-existing-models",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unrecognized arguments: --skip-existing-models", proc.stderr)


if __name__ == "__main__":
    unittest.main()
