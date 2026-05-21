import base64
import asyncio
import io
import mimetypes
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic_ai import Agent, BinaryContent, ModelSettings
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UserError,
)

from .config import ModelConfig, PromptsConfig

# Anthropic's 5MB limit applies to the base64 string, not raw bytes.
# base64 inflates by 4/3, so cap raw bytes at ~3.7MB to stay under 5MB encoded.
_MAX_IMAGE_BYTES = 3_700_000
_MAX_IMAGE_DIMENSION = 8_000
_MAX_ATTEMPTS = 3
_DEFAULT_TIMEOUT_SECONDS = 180
_STREAMING_MODEL_PREFIXES = ("google-gla:", "google-vertex:", "gemini:")
_MODEL_SETTINGS_KEYS = {
    "extra_body",
    "extra_headers",
    "frequency_penalty",
    "logit_bias",
    "max_tokens",
    "parallel_tool_calls",
    "presence_penalty",
    "seed",
    "service_tier",
    "stop_sequences",
    "temperature",
    "thinking",
    "timeout",
    "top_p",
}


@dataclass
class VisionResponse:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    latency_seconds: float = 0.0
    model_id: str = ""
    error: str | None = None


def _encode_image(image_path: Path) -> tuple[str, str]:
    with Image.open(image_path) as probe:
        width, height = probe.size

    within_dimension_limit = (
        width <= _MAX_IMAGE_DIMENSION and height <= _MAX_IMAGE_DIMENSION
    )
    raw = image_path.read_bytes()
    if len(raw) <= _MAX_IMAGE_BYTES and within_dimension_limit:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None:
            mime_type = "image/jpeg"
        return base64.b64encode(raw).decode("utf-8"), mime_type

    # Downscale until under both dimension and encoded-size limits.
    img = Image.open(image_path)
    if not within_dimension_limit:
        img.thumbnail((_MAX_IMAGE_DIMENSION, _MAX_IMAGE_DIMENSION), Image.LANCZOS)
    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if (
            buf.tell() <= _MAX_IMAGE_BYTES
            and img.width <= _MAX_IMAGE_DIMENSION
            and img.height <= _MAX_IMAGE_DIMENSION
        ):
            break
        # Reduce dimensions by 25%
        img = img.resize(
            (int(img.width * 0.75), int(img.height * 0.75)),
            Image.LANCZOS,
        )
        quality = max(quality - 5, 50)

    data = base64.b64encode(buf.getvalue()).decode("utf-8")
    return data, "image/jpeg"


def _model_settings(params: Mapping[str, Any]) -> tuple[ModelSettings, list[str]]:
    supported = {k: v for k, v in params.items() if k in _MODEL_SETTINGS_KEYS}
    unsupported = sorted(k for k in params if k not in _MODEL_SETTINGS_KEYS)
    supported.setdefault("timeout", _DEFAULT_TIMEOUT_SECONDS)
    return ModelSettings(**supported), unsupported


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        value = None
        if isinstance(usage, Mapping):
            value = usage.get(name)
        elif usage is not None:
            attr = getattr(usage, name, None)
            value = attr() if callable(attr) else attr
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _result_usage(result: Any) -> Any:
    return getattr(result, "usage", None)


def _result_cost(result: Any) -> float:
    try:
        response = getattr(result, "response", None)
        if response is None:
            return 0.0
        cost = response.cost()
        return float(getattr(cost, "total_price", 0.0) or 0.0)
    except Exception:
        return 0.0


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, ModelHTTPError):
        return exc.status_code == 429 or exc.status_code >= 500

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    retry_markers = (
        "apiconnectionerror",
        "connectionerror",
        "connection error",
        "connection reset",
        "incomplete read",
        "network",
        "rate limit",
        "ratelimit",
        "remoteprotocolerror",
        "server disconnected",
        "service unavailable",
        "timeout",
        "timed out",
    )
    return any(marker in name or marker in text for marker in retry_markers)


def _should_stream_model(model_id: str) -> bool:
    return model_id.startswith(_STREAMING_MODEL_PREFIXES)


async def _run_agent(agent: Agent, prompt: list[Any], settings: ModelSettings, stream: bool) -> Any:
    if stream and hasattr(agent, "run_stream"):
        async with agent.run_stream(prompt, model_settings=settings) as result:
            async for _text in result.stream_text():
                pass
            return result

    return await agent.run(prompt, model_settings=settings)


def _format_model_error(
    exc: Exception,
    model: ModelConfig,
    unsupported_params: list[str],
) -> str:
    parts = [
        f"PydanticAI request failed for {model.label} ({model.id})",
        f"{type(exc).__name__}: {exc}",
    ]

    if isinstance(exc, ModelHTTPError):
        parts.append(f"HTTP status: {exc.status_code}")
        if exc.body:
            parts.append(f"response body: {exc.body}")
    elif isinstance(exc, ModelAPIError):
        api_model = getattr(exc, "model_name", "")
        if api_model:
            parts.append(f"provider model: {api_model}")
    elif isinstance(exc, UnexpectedModelBehavior) and getattr(exc, "body", None):
        parts.append(f"response body: {exc.body}")

    if unsupported_params:
        parts.append(f"ignored unsupported model params: {', '.join(unsupported_params)}")

    lowered = " ".join(str(part).lower() for part in parts)
    if isinstance(exc, UserError) or "unknown provider" in lowered or "model id" in lowered:
        parts.append("hint: use PydanticAI model IDs such as openai:gpt-5.2, anthropic:claude-sonnet-4-6, or google-gla:gemini-2.5-flash")
    elif "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        parts.append("hint: check the provider API key environment variable loaded by .env")
    elif "image" in lowered or "binarycontent" in lowered or "media" in lowered:
        parts.append("hint: confirm this model supports image input through PydanticAI")
    elif "timeout" in lowered or "timed out" in lowered:
        parts.append("hint: increase the model timeout or lower bench.max_concurrency")
    elif "rate limit" in lowered or "429" in lowered:
        parts.append("hint: lower bench.max_concurrency or add a provider cooldown")
    elif "setting" in lowered or "parameter" in lowered or "unexpected keyword" in lowered:
        parts.append("hint: check this model's PydanticAI ModelSettings")

    return "; ".join(parts)


async def call_vision_model(
    model: ModelConfig,
    image_path: Path,
    prompts: PromptsConfig,
) -> VisionResponse:
    start = time.monotonic()
    try:
        b64_data, mime_type = _encode_image(image_path)
        image_content = BinaryContent(
            data=base64.b64decode(b64_data),
            media_type=mime_type,
        )
        settings, unsupported_params = _model_settings(model.params)

        result = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                agent = Agent(model.id, system_prompt=prompts.system)
                async with agent:
                    result = await _run_agent(
                        agent,
                        [prompts.user, image_content],
                        settings,
                        _should_stream_model(model.id),
                    )
                break
            except Exception as e:
                if not _is_retryable_error(e) or attempt == _MAX_ATTEMPTS - 1:
                    raise
                delay = 2**attempt
                print(
                    f"  RETRY [{model.label}] attempt {attempt + 2}/{_MAX_ATTEMPTS} "
                    f"after {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                await asyncio.sleep(delay)

        latency = time.monotonic() - start

        usage = _result_usage(result)
        input_tokens = _usage_value(usage, "input_tokens", "request_tokens")
        output_tokens = _usage_value(usage, "output_tokens", "response_tokens")
        return VisionResponse(
            text=str(getattr(result, "output", "") or ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=_usage_value(usage, "total_tokens") or input_tokens + output_tokens,
            cost=_result_cost(result),
            latency_seconds=round(latency, 3),
            model_id=model.label,
        )
    except Exception as e:
        unsupported_params = sorted(k for k in model.params if k not in _MODEL_SETTINGS_KEYS)
        error = _format_model_error(e, model, unsupported_params)
        print(f"  ERROR [{model.label}]: {error}", file=sys.stderr)
        return VisionResponse(
            model_id=model.label,
            latency_seconds=round(time.monotonic() - start, 3),
            error=error,
        )
