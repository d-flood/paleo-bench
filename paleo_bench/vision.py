import base64
import io
import mimetypes
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import litellm
from PIL import Image

from .config import ModelConfig, PromptsConfig

# Anthropic's 5MB limit applies to the base64 string, not raw bytes.
# base64 inflates by 4/3, so cap raw bytes at ~3.7MB to stay under 5MB encoded.
_MAX_IMAGE_BYTES = 3_700_000
_MAX_IMAGE_DIMENSION = 8_000


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


async def call_vision_model(
    model: ModelConfig,
    image_path: Path,
    prompts: PromptsConfig,
) -> VisionResponse:
    try:
        b64_data, mime_type = _encode_image(image_path)
        data_url = f"data:{mime_type};base64,{b64_data}"

        messages = [
            {"role": "system", "content": prompts.system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompts.user},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ]

        start = time.monotonic()
        response = await litellm.acompletion(
            model=model.id,
            messages=messages,
            **model.params,
        )
        latency = time.monotonic() - start

        usage = getattr(response, "usage", None)
        choices = getattr(response, "choices", None)
        if not choices:
            return VisionResponse(
                model_id=model.label,
                error="No choices in response",
            )
        choice = choices[0]
        text = getattr(choice, "message", None)
        hidden = getattr(response, "_hidden_params", {})
        cost = hidden.get("response_cost", 0.0) or 0.0
        return VisionResponse(
            text=getattr(text, "content", "") or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            cost=cost,
            latency_seconds=round(latency, 3),
            model_id=model.label,
        )
    except Exception as e:
        print(f"  ERROR [{model.label}]: {type(e).__name__}: {e}", file=sys.stderr)
        return VisionResponse(
            model_id=model.label,
            error=f"{type(e).__name__}: {e}",
        )
