import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from paleo_bench.iiif import fetch_iiif_image


class _MockResponse:
    def __init__(self, status_code: int, *, json_data=None, content: bytes = b"") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.content = content

    def json(self):
        return self._json_data


class _MockClient:
    def __init__(self, responses: dict[str, _MockResponse]) -> None:
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str) -> _MockResponse:
        return self._responses[url]


def _jpeg_bytes(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="JPEG")
    return buf.getvalue()


class TestIiifSide(unittest.TestCase):
    def test_fetch_iiif_image_crops_verso_and_recto(self) -> None:
        info_url = "https://example.org/iiif/a/info.json"
        base = "https://example.org/iiif/a"
        image_url = f"{base}/full/max/0/default.jpg"
        responses = {
            info_url: _MockResponse(200, json_data={"id": base, "type": "ImageService3"}),
            image_url: _MockResponse(200, content=_jpeg_bytes(11, 7)),
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            with patch(
                "paleo_bench.iiif.httpx.Client",
                return_value=_MockClient(responses),
            ):
                verso = fetch_iiif_image(info_url, cache_dir, side="verso")
                recto = fetch_iiif_image(info_url, cache_dir, side="recto")
                full = fetch_iiif_image(info_url, cache_dir, side=None)

            with Image.open(verso) as im_verso:
                self.assertEqual(im_verso.size, (5, 7))
            with Image.open(recto) as im_recto:
                self.assertEqual(im_recto.size, (6, 7))
            with Image.open(full) as im_full:
                self.assertEqual(im_full.size, (11, 7))
            self.assertNotEqual(verso, recto)
            self.assertNotEqual(full, verso)
            self.assertNotEqual(full, recto)

    def test_fetch_iiif_image_uses_side_in_cache_key(self) -> None:
        info_url = "https://example.org/iiif/a/info.json"
        base = "https://example.org/iiif/a"
        image_url = f"{base}/full/max/0/default.jpg"
        responses = {
            info_url: _MockResponse(200, json_data={"id": base, "type": "ImageService3"}),
            image_url: _MockResponse(200, content=_jpeg_bytes(10, 4)),
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            with patch(
                "paleo_bench.iiif.httpx.Client",
                return_value=_MockClient(responses),
            ):
                first = fetch_iiif_image(info_url, cache_dir, side="verso")
                second = fetch_iiif_image(info_url, cache_dir, side="verso")
                recto = fetch_iiif_image(info_url, cache_dir, side="recto")

        self.assertEqual(first, second)
        self.assertNotEqual(first, recto)


if __name__ == "__main__":
    unittest.main()
