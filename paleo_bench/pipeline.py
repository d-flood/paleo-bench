import asyncio
import json
import re
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import NativeOutput

from .config import ModelConfig, PipelineConfig, PromptsConfig
from .metrics import regularize_for_scoring
from .vision import (
    VisionResponse,
    _error_response,
    _image_content,
    _request,
    _request_settings,
    _vision_response,
)

_COLUMN_LABEL = re.compile(r"^\s*Column \d+\s*$")


class Correction(BaseModel):
    id: str
    text: str
    change: str


class Corrections(BaseModel):
    corrections: list[Correction]


def _numbered_lines(text: str) -> Iterator[tuple[int | None, str]]:
    n = 0
    for line in text.split("\n"):
        if not line.strip() or _COLUMN_LABEL.match(line):
            yield None, line
        else:
            n += 1
            yield n, line


def word_ids(text: str) -> dict[str, str]:
    return {
        f"L{n}.{k}": word
        for n, line in _numbered_lines(text)
        if n is not None
        for k, word in enumerate(line.split(), 1)
    }


def merge(text: str, corrections: dict[str, str]) -> str:
    lines = []
    for n, line in _numbered_lines(text):
        if n is None:
            lines.append(line)
            continue
        words = (corrections.get(f"L{n}.{k}", word) for k, word in enumerate(line.split(), 1))
        lines.append(" ".join(word for word in words if word))
    return "\n".join(lines)


def vote(checks: list[list[Correction]], votes: int) -> dict[str, str]:
    counts: Counter[tuple[str, str]] = Counter()
    texts: dict[tuple[str, str], str] = {}
    for check in checks:
        keys = {(c.id, regularize_for_scoring(c.text.strip())): c.text.strip() for c in check}
        counts.update(keys.keys())
        for key, text in keys.items():
            texts.setdefault(key, text)
    agreed = sorted((n, key) for key, n in counts.items() if n >= votes)
    return {key[0]: texts[key] for _n, key in agreed}


async def call_vote_pipeline(
    model: ModelConfig,
    image_path: Path,
    prompts: PromptsConfig,
    pipeline: PipelineConfig,
    lectionary: bool,
) -> VisionResponse:
    start = time.monotonic()
    try:
        spec = model.params["pipeline"]
        image = _image_content(model, image_path)
        settings = _request_settings(model)
        notes = pipeline.lectionary_notes if lectionary else pipeline.continuous_notes
        draft = await _request(
            model,
            f"{prompts.system}\n{notes}",
            [prompts.user, image],
            settings,
            start,
        )
        draft_text = str(draft.output or "")

        check_settings = dict(settings)
        if "check_thinking" in spec:
            check_settings["thinking"] = spec["check_thinking"]
        check_prompt = [
            pipeline.check_user + json.dumps(word_ids(draft_text), ensure_ascii=False, indent=0),
            image,
        ]
        checks = await asyncio.gather(
            *(
                _request(
                    model,
                    pipeline.check_system,
                    check_prompt,
                    check_settings,
                    start,
                    NativeOutput(Corrections),
                )
                for _ in range(spec["checks"])
            )
        )
        corrections = vote([check.output.corrections for check in checks], spec["votes"])
        return _vision_response(model, merge(draft_text, corrections), [draft, *checks], start)
    except Exception as e:
        return _error_response(model, e, start)
