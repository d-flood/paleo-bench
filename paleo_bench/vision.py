import base64
import asyncio
import io
import mimetypes
import os
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
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import ModelConfig, PromptsConfig

# Anthropic's 5MB limit applies to the base64 string, not raw bytes.
# base64 inflates by 4/3, so cap raw bytes at ~3.7MB to stay under 5MB encoded.
_MAX_IMAGE_BYTES = 3_700_000
_MAX_IMAGE_DIMENSION = 8_000
_MAX_ATTEMPTS = 3
_DEFAULT_TIMEOUT_SECONDS = 180
_RESAMPLE_FILTER = Image.Resampling.LANCZOS
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
_IMAGE_SETTINGS_KEYS = {"image_max_bytes", "image_max_dimension"}
_COST_SETTINGS_KEYS = {"input_token_cost", "output_token_cost"}
_SUPPORTED_MODEL_PARAM_KEYS = _MODEL_SETTINGS_KEYS | _IMAGE_SETTINGS_KEYS | _COST_SETTINGS_KEYS


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


class HardRequestTimeoutError(TimeoutError):
    pass


def _encode_image(
    image_path: Path,
    *,
    max_bytes: int = _MAX_IMAGE_BYTES,
    max_dimension: int = _MAX_IMAGE_DIMENSION,
) -> tuple[str, str]:
    with Image.open(image_path) as probe:
        width, height = probe.size

    within_dimension_limit = width <= max_dimension and height <= max_dimension
    raw = image_path.read_bytes()
    if len(raw) <= max_bytes and within_dimension_limit:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None:
            mime_type = "image/jpeg"
        return base64.b64encode(raw).decode("utf-8"), mime_type

    # Downscale until under both dimension and encoded-size limits.
    img = Image.open(image_path)
    if not within_dimension_limit:
        img.thumbnail((max_dimension, max_dimension), _RESAMPLE_FILTER)
    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if (
            buf.tell() <= max_bytes
            and img.width <= max_dimension
            and img.height <= max_dimension
        ):
            break
        # Reduce dimensions by 25%
        img = img.resize(
            (int(img.width * 0.75), int(img.height * 0.75)),
            _RESAMPLE_FILTER,
        )
        quality = max(quality - 5, 50)

    data = base64.b64encode(buf.getvalue()).decode("utf-8")
    return data, "image/jpeg"


def _model_settings(params: Mapping[str, Any]) -> tuple[ModelSettings, list[str]]:
    supported = {k: v for k, v in params.items() if k in _MODEL_SETTINGS_KEYS}
    unsupported = sorted(k for k in params if k not in _SUPPORTED_MODEL_PARAM_KEYS)
    supported.setdefault("timeout", _DEFAULT_TIMEOUT_SECONDS)
    return ModelSettings(**supported), unsupported


def _image_limits(params: Mapping[str, Any]) -> tuple[int, int]:
    max_bytes = params.get("image_max_bytes", _MAX_IMAGE_BYTES)
    max_dimension = params.get("image_max_dimension", _MAX_IMAGE_DIMENSION)
    try:
        parsed_max_bytes = int(max_bytes)
        parsed_max_dimension = int(max_dimension)
    except (TypeError, ValueError):
        return _MAX_IMAGE_BYTES, _MAX_IMAGE_DIMENSION
    return parsed_max_bytes, parsed_max_dimension


def _settings_timeout_seconds(settings: ModelSettings) -> float:
    value = settings.get("timeout") if isinstance(settings, Mapping) else None
    try:
        return float(value or _DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return float(_DEFAULT_TIMEOUT_SECONDS)


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        value: Any = None
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


def _configured_cost(params: Mapping[str, Any], input_tokens: int, output_tokens: int) -> float:
    try:
        input_token_cost = float(params.get("input_token_cost", 0.0) or 0.0)
        output_token_cost = float(params.get("output_token_cost", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return input_tokens * input_token_cost + output_tokens * output_token_cost


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, HardRequestTimeoutError):
        return False

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


_OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _make_agent(model_id: str, system_prompt: str) -> Agent:
    if model_id.startswith("opencode-go:"):
        model_name = model_id.split(":", 1)[1]
        pydantic_model = OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=_OPENCODE_GO_BASE_URL,
                api_key=os.environ.get("OPENCODE_GO_API_KEY"),
            ),
        )
        return Agent(pydantic_model, system_prompt=system_prompt)
    if model_id.startswith("openrouter:"):
        model_name = model_id.split(":", 1)[1]
        pydantic_model = OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=_OPENROUTER_BASE_URL,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
            ),
        )
        return Agent(pydantic_model, system_prompt=system_prompt)
    return Agent(model_id, system_prompt=system_prompt)


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
        image_max_bytes, image_max_dimension = _image_limits(model.params)
        b64_data, mime_type = _encode_image(
            image_path,
            max_bytes=image_max_bytes,
            max_dimension=image_max_dimension,
        )
        print(
            f"  IMAGE [{model.label}] encoded {len(b64_data):,} base64 chars "
            f"as {mime_type}",
            file=sys.stderr,
        )
        image_content = BinaryContent(
            data=base64.b64decode(b64_data),
            media_type=mime_type,
        )
        settings, unsupported_params = _model_settings(model.params)

        result = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                agent = _make_agent(model.id, prompts.system)
                async with agent:
                    timeout_seconds = _settings_timeout_seconds(settings)
                    print(
                        f"  REQUEST [{model.label}] attempt {attempt + 1}/{_MAX_ATTEMPTS} "
                        f"with hard timeout {timeout_seconds:g}s",
                        file=sys.stderr,
                    )
                    try:
                        result = await asyncio.wait_for(
                            _run_agent(
                                agent,
                                [prompts.user, image_content],
                                settings,
                                _should_stream_model(model.id),
                            ),
                            timeout=timeout_seconds,
                        )
                    except asyncio.TimeoutError as e:
                        raise HardRequestTimeoutError(
                            f"request exceeded hard timeout of {timeout_seconds:g}s"
                        ) from e
                    print(
                        f"  RESPONSE [{model.label}] received after "
                        f"{time.monotonic() - start:.1f}s",
                        file=sys.stderr,
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
        cost = _result_cost(result) or _configured_cost(
            model.params,
            input_tokens,
            output_tokens,
        )
        return VisionResponse(
            text=str(getattr(result, "output", "") or ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=_usage_value(usage, "total_tokens") or input_tokens + output_tokens,
            cost=cost,
            latency_seconds=round(latency, 3),
            model_id=model.label,
        )
    except Exception as e:
        unsupported_params = sorted(
            k for k in model.params if k not in _SUPPORTED_MODEL_PARAM_KEYS
        )
        error = _format_model_error(e, model, unsupported_params)
        print(f"  ERROR [{model.label}]: {error}", file=sys.stderr)
        return VisionResponse(
            model_id=model.label,
            latency_seconds=round(time.monotonic() - start, 3),
            error=error,
        )
