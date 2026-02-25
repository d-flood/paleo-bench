import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


class ConfigError(Exception):
    pass


@dataclass
class ModelConfig:
    id: str
    label: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class SampleConfig:
    image_url: str
    ground_truth: Path
    label: str = ""
    side: Literal["verso", "recto"] | None = None
    cached_image: Path | None = None


@dataclass
class GroupConfig:
    name: str
    samples: list[SampleConfig] = field(default_factory=list)


@dataclass
class PromptsConfig:
    system: str
    user: str


@dataclass
class BenchConfig:
    name: str
    output: Path
    max_concurrency: int
    prompts: PromptsConfig
    models: list[ModelConfig]
    groups: list[GroupConfig]


def load_config(path: "str | Path") -> BenchConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    base_dir = path.parent

    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}") from e

    # [bench]
    bench = raw.get("bench")
    if not bench:
        raise ConfigError("Missing [bench] section")
    name = bench.get("name", "Paleo Benchmark Run")
    output = Path(bench.get("output", "results.json"))
    max_concurrency = bench.get("max_concurrency", 5)

    # [prompts]
    prompts_raw = raw.get("prompts")
    if not prompts_raw:
        raise ConfigError("Missing [prompts] section")
    for key in ("system", "user"):
        if key not in prompts_raw:
            raise ConfigError(f"Missing prompts.{key}")
    prompts = PromptsConfig(system=prompts_raw["system"], user=prompts_raw["user"])

    # [[models]]
    models_raw = raw.get("models")
    if not models_raw:
        raise ConfigError("No [[models]] defined")
    models = []
    for m in models_raw:
        if "id" not in m:
            raise ConfigError("Each [[models]] entry requires an 'id' field")
        label = m.get("label", m["id"])
        params = {k: v for k, v in m.items() if k not in ("id", "label")}
        models.append(ModelConfig(id=m["id"], label=label, params=params))

    labels = [m.label for m in models]
    if len(labels) != len(set(labels)):
        seen = set()
        dupes = [l for l in labels if l in seen or seen.add(l)]
        raise ConfigError(f"Duplicate model labels: {', '.join(dupes)}")

    # [[groups]]
    groups_raw = raw.get("groups")
    if not groups_raw:
        raise ConfigError("No [[groups]] defined")

    groups = []
    for g in groups_raw:
        if "name" not in g:
            raise ConfigError("Each [[groups]] entry requires a 'name' field")
        samples = []
        for s in g.get("samples", []):
            if "image" not in s:
                raise ConfigError(f"Sample in group '{g['name']}' missing 'image'")
            if "ground_truth" not in s:
                raise ConfigError(f"Sample in group '{g['name']}' missing 'ground_truth'")
            image_url = s["image"]
            if not re.match(r"https?://", image_url):
                raise ConfigError(
                    f"Image URL must start with http:// or https://: {image_url}"
                )
            if not image_url.endswith("/info.json"):
                raise ConfigError(
                    f"Image URL must end with /info.json: {image_url}"
                )
            gt_path = base_dir / s["ground_truth"]
            if not gt_path.exists():
                raise ConfigError(f"Ground truth file not found: {gt_path}")
            label = s.get("label", "")
            side = s.get("side")
            if side is not None:
                if side not in ("verso", "recto"):
                    raise ConfigError(
                        f"Sample in group '{g['name']}' has invalid side '{side}'; expected 'verso' or 'recto'"
                    )
            samples.append(
                SampleConfig(
                    image_url=image_url,
                    ground_truth=gt_path,
                    label=label,
                    side=side,
                )
            )
        groups.append(GroupConfig(name=g["name"], samples=samples))

    return BenchConfig(
        name=name,
        output=output,
        max_concurrency=max_concurrency,
        prompts=prompts,
        models=models,
        groups=groups,
    )
