# htr-bench

Static SvelteKit site for viewing benchmark output stored in `static/results.json`.

At build/dev startup, `scripts/split-results-for-site.mjs` derives lightweight site artifacts:

- `static/site-data/summary.json`: models, folios and per-folio metrics for the results, graphs and by-folio pages
- `static/site-data/folio/*.json`: ground truth and every model's transcription for one folio, loaded by the image & transcription page

Scoring strips accents and punctuation, ignores capitalization, reads every sigma form as σ, folds Greek letter variants (ϑ, ϐ, ϰ, ϱ, ϕ, ϖ, ϵ) to their usual forms, expands ϛ, ȣ and ϗ to στ, ου and και, and maps Latin or Cyrillic look-alike letters inside Greek words to Greek. Stored transcriptions keep their original case and sigma forms. Mark a sample with `microfilm = true` in the config to report it separately from colour images.

## Local development

```sh
pnpm install --frozen-lockfile
pnpm dev
```

## Build

```sh
pnpm build
```

The build runs `scripts/split-results-for-site.mjs` before `vite build`, generating
`static/site-data/*` from the current `static/results.json`.

## Update benchmark results

Install [uv](https://docs.astral.sh/uv/) and prepare the Python environment:

```sh
uv sync --locked
cp .env.example .env
```

Add these keys to the root `.env` (ignored by Git):

| Secret               | Provider                                                                             |
| -------------------- | ------------------------------------------------------------------------------------ |
| `ANTHROPIC_API_KEY`  | [Anthropic Console](https://platform.claude.com/settings/keys)                       |
| `OPENAI_API_KEY`     | [OpenAI API](https://platform.openai.com/api-keys)                                   |
| `GEMINI_API_KEY`     | [Google AI Studio](https://aistudio.google.com/apikey)                               |
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai/settings/keys), for all hosted open-weight models |

For an Anthropic key that spans workspaces, also set `ANTHROPIC_WORKSPACE_ID` from [workspace settings](https://platform.claude.com/settings/workspaces).

Validate without API calls, then run:

```sh
uv run python -m paleo_bench --config config.toml --dry-run
uv run python -m paleo_bench --config config.toml
```

The October 2026 configuration includes:

- Claude Opus, Sonnet, and Haiku 5.5 ([Anthropic models](https://platform.claude.com/docs/en/models/overview)).
- GPT-6 Astra, GPT-6.1 Sol, and GPT-6 Luna ([OpenAI Docs](https://developers.openai.com/api/docs/models)).
- [Gemini 4 Argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon) and [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
- Open weights: [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3), [GLM 5.3 Flash](https://huggingface.co/zai-org/GLM-5.3-Flash), [DeepSeek V4.1 Flash 1017](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017), [Qwen 3.8 27B](https://huggingface.co/Qwen/Qwen3.8-27B), [Nemotron 3.5 Super VL](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16), and [Muse Spark Open](https://research.meta.ai/blog/muse-spark-open), hosted through [OpenRouter](https://openrouter.ai/api/v1/models).

Direct-provider models run at low and high thinking levels, except Astra, which
runs at low after three high-thinking requests timed out at 20 minutes. Its
failed attempts remain in the saved results. Opus and Sonnet 5.5 cannot disable
thinking. OpenRouter token prices are fallback estimates from its
October 22 catalogue; routing and pricing can change. Account access is checked
only when you run the benchmark.

DeepSeek, Kimi, and Nemotron disable thinking for transcription after reasoning
runs exhausted their token budgets on some folios. Those earlier results are
retained separately for comparison.

Existing completed results are retained when resuming. No benchmark API keys are
needed in GitHub Actions; deployment builds the saved static results.

Benchmark execution is manual. The runner merges new results into
`static/results.json`, preserving saved runs. After running the benchmark locally:

1. Run `pnpm gen:site-data` (or run `pnpm build`, which generates site data automatically).
2. Commit the updated `static/results.json` and generated `static/site-data/*`.
3. Push to `main` to trigger deployment.

If you edited only ground-truth text and want to recompute comparisons without calling models again:

```sh
uv run python -m paleo_bench --config config.toml --recompute-comparisons
```

This recalculates per-row metrics plus model/group summaries from existing `static/results.json`.

## PydanticAI model settings

Slow vision/reasoning models can exceed the default request timeout. Extra keys in
each `[[models]]` entry are interpreted as PydanticAI `ModelSettings`, so use
PydanticAI model IDs and set per-model settings in TOML:

```toml
[[models]]
id = "anthropic:claude-opus-5-5"
label = "Opus 5.5 (high)"
timeout = 300
thinking = "high"
```

Use `openai-chat:` for OpenAI Chat Completions models, for example
`openai-chat:gpt-6.1-sol`.

If several providers are timing out, also try lowering `[bench].max_concurrency`
to reduce concurrent connection pressure.

For resume runs where only one provider has failed rows left, add provider
cooldowns so other providers can run while repeated calls wait:

```toml
[bench.provider_cooldown_seconds]
anthropic = 10
openai = 60
google = 30
```
