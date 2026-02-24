import base64
import sys
import tempfile
import types
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.modules.setdefault("litellm", types.SimpleNamespace(acompletion=None))

from paleo_bench.vision import _MAX_IMAGE_DIMENSION, _encode_image


class TestVisionEncoding(unittest.TestCase):
    def test_oversized_dimensions_are_resized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "oversized.png"
            Image.new("RGB", (_MAX_IMAGE_DIMENSION + 500, 1200), "white").save(
                image_path, format="PNG"
            )

            encoded, mime_type = _encode_image(image_path)

            self.assertEqual(mime_type, "image/jpeg")
            decoded = base64.b64decode(encoded)
            # Read dimensions from encoded image bytes.
            with Image.open(BytesIO(decoded)) as resized:
                self.assertLessEqual(resized.width, _MAX_IMAGE_DIMENSION)
                self.assertLessEqual(resized.height, _MAX_IMAGE_DIMENSION)


if __name__ == "__main__":
    unittest.main()
