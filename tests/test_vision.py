import base64
import tempfile
import types
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from paleo_bench.config import ModelConfig, PromptsConfig
from paleo_bench.vision import (
    _DEFAULT_TIMEOUT_SECONDS,
    _MAX_IMAGE_DIMENSION,
    call_vision_model,
    _encode_image,
)


class Timeout(Exception):
    pass


class FakeResult:
    output = "transcription"
    usage = types.SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3)
    response = types.SimpleNamespace(
        cost=lambda: types.SimpleNamespace(total_price=0.01),
    )


class FakeFreeResult:
    output = "transcription"
    usage = types.SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120)
    response = types.SimpleNamespace(
        cost=lambda: types.SimpleNamespace(total_price=0.0),
    )


class FakeAgent:
    calls = []
    results = []
    stream_results = []

    def __init__(self, model_id, **kwargs):
        self.model_id = model_id
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def run(self, prompt, **kwargs):
        self.calls.append(
            {
                "method": "run",
                "model_id": self.model_id,
                "agent_kwargs": self.kwargs,
                "prompt": prompt,
                **kwargs,
            }
        )
        result = self.results.pop(0) if self.results else FakeResult()
        if isinstance(result, Exception):
            raise result
        return result

    def run_stream(self, prompt, **kwargs):
        self.calls.append(
            {
                "method": "run_stream",
                "model_id": self.model_id,
                "agent_kwargs": self.kwargs,
                "prompt": prompt,
                **kwargs,
            }
        )
        result = self.stream_results.pop(0) if self.stream_results else FakeResult()
        if isinstance(result, Exception):
            raise result
        return FakeStreamResult(result)


class FakeStreamResult:
    def __init__(self, result):
        self._result = result

    async def __aenter__(self):
        return self._result

    async def __aexit__(self, *_args):
        return None


async def _stream_text(_self):
    yield "transcription"


FakeResult.stream_text = _stream_text


async def _no_sleep(_delay: float) -> None:
    pass


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


class TestVisionModelCall(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.image_path = Path(self.tmp.name) / "sample.png"
        Image.new("RGB", (8, 8), "white").save(self.image_path, format="PNG")
        self.prompts = PromptsConfig(system="system", user="user")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _patch_agent(self, *results):
        FakeAgent.calls = []
        FakeAgent.results = list(results)
        FakeAgent.stream_results = []
        return patch("paleo_bench.vision.Agent", FakeAgent)

    def _patch_streaming_agent(self, *results):
        FakeAgent.calls = []
        FakeAgent.results = []
        FakeAgent.stream_results = list(results)
        return patch("paleo_bench.vision.Agent", FakeAgent)

    async def test_uses_default_timeout(self) -> None:
        with self._patch_agent():
            response = await call_vision_model(
                ModelConfig(id="test/model", label="test"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(FakeAgent.calls[0]["model_settings"]["timeout"], _DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(response.cost, 0.01)

    async def test_preserves_configured_timeout(self) -> None:
        model = ModelConfig(id="test/model", label="test", params={"timeout": 300})
        with self._patch_agent():
            response = await call_vision_model(model, self.image_path, self.prompts)

        self.assertIsNone(response.error)
        self.assertEqual(FakeAgent.calls[0]["model_settings"]["timeout"], 300)

    async def test_uses_configured_cost_when_provider_cost_missing(self) -> None:
        model = ModelConfig(
            id="openrouter:test/model",
            label="test",
            params={"input_token_cost": 0.001, "output_token_cost": 0.01},
        )
        with self._patch_agent(FakeFreeResult()):
            response = await call_vision_model(model, self.image_path, self.prompts)

        self.assertIsNone(response.error)
        self.assertAlmostEqual(response.cost, 0.3)

    async def test_retries_timeout_error(self) -> None:
        with (
            self._patch_agent(Timeout("connection timed out"), FakeResult()),
            patch("paleo_bench.vision.asyncio.sleep", _no_sleep),
        ):
            response = await call_vision_model(
                ModelConfig(id="test/model", label="test"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "transcription")
        self.assertEqual(len(FakeAgent.calls), 2)

    async def test_streams_google_models(self) -> None:
        with self._patch_streaming_agent(FakeResult()):
            response = await call_vision_model(
                ModelConfig(id="google-gla:gemini-3.5-flash", label="gemini"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "transcription")
        self.assertEqual(FakeAgent.calls[0]["method"], "run_stream")

    async def test_retries_remote_protocol_error(self) -> None:
        class RemoteProtocolError(Exception):
            pass

        with (
            self._patch_agent(RemoteProtocolError("server disconnected"), FakeResult()),
            patch("paleo_bench.vision.asyncio.sleep", _no_sleep),
        ):
            response = await call_vision_model(
                ModelConfig(id="test/model", label="test"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "transcription")
        self.assertEqual(len(FakeAgent.calls), 2)

    async def test_does_not_retry_non_retryable_error(self) -> None:
        with self._patch_agent(ValueError("bad request")):
            response = await call_vision_model(
                ModelConfig(id="test/model", label="test"),
                self.image_path,
                self.prompts,
            )

        self.assertEqual(len(FakeAgent.calls), 1)
        self.assertIn("test (test/model)", response.error)
        self.assertIn("ValueError: bad request", response.error)

    async def test_error_mentions_unsupported_params(self) -> None:
        model = ModelConfig(
            id="openai:gpt-test",
            label="test",
            params={"api_base": "https://example.invalid"},
        )
        with self._patch_agent(ValueError("bad request")):
            response = await call_vision_model(model, self.image_path, self.prompts)

        self.assertIn("ignored unsupported model params: api_base", response.error)

    async def test_opencode_go_model_routing(self) -> None:
        with self._patch_agent(), patch.dict("os.environ", {"OPENCODE_GO_API_KEY": "test-key"}):
            response = await call_vision_model(
                ModelConfig(id="opencode-go:qwen3.6-plus", label="qwen3.6-plus"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "transcription")
        self.assertEqual(response.model_id, "qwen3.6-plus")
        self.assertIn("system_prompt", FakeAgent.calls[0]["agent_kwargs"])

    async def test_openrouter_model_routing(self) -> None:
        with self._patch_agent(), patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            response = await call_vision_model(
                ModelConfig(id="openrouter:qwen/qwen3.6-plus", label="Qwen 3.6 Plus"),
                self.image_path,
                self.prompts,
            )

        self.assertIsNone(response.error)
        self.assertEqual(response.text, "transcription")
        self.assertEqual(response.model_id, "Qwen 3.6 Plus")
        self.assertIn("system_prompt", FakeAgent.calls[0]["agent_kwargs"])


if __name__ == "__main__":
    unittest.main()
