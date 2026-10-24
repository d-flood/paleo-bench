import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';

const resultsPath = resolve(process.cwd(), 'static/results.json');
const outDir = resolve(process.cwd(), 'static/site-data');
const folioDir = resolve(outDir, 'folio');

const PROVIDERS = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  'openai-chat': 'OpenAI',
  google: 'Google',
  'google-gla': 'Google',
  openrouter: 'OpenRouter'
};

function stableSampleId(group, label, image) {
  return createHash('sha1').update(`${group}::${label}::${image}`).digest('hex').slice(0, 12);
}

function readResults() {
  try {
    return JSON.parse(readFileSync(resultsPath, 'utf-8'));
  } catch (error) {
    console.error(`Failed to read ${resultsPath}:`, error);
    process.exit(1);
  }
}

function writeJson(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(data)}\n`, 'utf-8');
}

function slug(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function splitLabel(label) {
  const [ms, folio, ...rest] = label.split(',').map((part) => part.trim());
  return rest.length
    ? { ms, folio, passage: rest.join(', ') }
    : { ms: label, folio: '', passage: '' };
}

const data = readResults();
const benchmark = data.benchmark ?? {};
const summaries = data.model_summaries ?? {};
const configModels = benchmark.config?.models ?? [];
const results = data.results ?? [];

const models = configModels
  .map((m) => {
    const s = summaries[m.label] ?? {};
    const thinking = /\((low|high|thinking|no thinking|multi-step)\)$/.exec(m.label)?.[1] ?? null;
    const prefix = String(m.id ?? '').split(/[:/]/)[0];
    return {
      label: m.label,
      slug: slug(m.label),
      provider: PROVIDERS[prefix] ?? 'Other',
      openWeights: m.open_weights === true,
      thinking,
      cer: s.samples_evaluated ? s.cer_mean : null,
      wer: s.samples_evaluated ? s.wer_mean : null,
      read: s.samples_evaluated ?? 0,
      failed: s.samples_failed ?? 0,
      cost: s.total_cost ?? 0,
      latency: s.total_latency_seconds ?? 0,
      outTokens: s.total_output_tokens ?? 0
    };
  })
  .sort((a, b) => (a.cer ?? Infinity) - (b.cer ?? Infinity) || a.label.localeCompare(b.label));

const samples = new Map();
for (const row of results) {
  const id = stableSampleId(row.group ?? '', row.label ?? '', row.image ?? '');
  if (!samples.has(id)) {
    samples.set(id, {
      id,
      group: row.group ?? '',
      label: row.label ?? '',
      ...splitLabel(row.label ?? ''),
      microfilm: row.microfilm === true,
      lectionary: row.lectionary === true,
      side: row.side ?? null,
      image: row.image ?? '',
      order: Number.isFinite(row.sample_order) ? row.sample_order : Infinity,
      chars: null,
      results: {},
      gt: row.ground_truth_text ?? '',
      texts: {}
    });
  }
  const sample = samples.get(id);
  const metrics = row.metrics ?? null;
  const meta = row.response_metadata ?? {};
  if (metrics && sample.chars == null) sample.chars = metrics.char_count_reference;
  sample.results[row.model] = {
    cer: metrics?.cer ?? null,
    wer: metrics?.wer ?? null,
    cost: meta.cost ?? null,
    latency: meta.latency_seconds ?? null,
    outTokens: meta.output_tokens ?? null,
    error: row.error ?? null
  };
  if (!row.error && row.model_output) sample.texts[row.model] = row.model_output;
}

const ordered = [...samples.values()].sort(
  (a, b) => a.order - b.order || a.label.localeCompare(b.label)
);

rmSync(outDir, { recursive: true, force: true });
mkdirSync(folioDir, { recursive: true });

for (const s of ordered) {
  writeJson(resolve(folioDir, `${s.id}.json`), { id: s.id, gt: s.gt, texts: s.texts });
}

writeJson(resolve(outDir, 'summary.json'), {
  name: benchmark.name,
  timestamp: benchmark.timestamp,
  groups: [...new Set(ordered.map((s) => s.group))],
  models,
  samples: ordered.map(({ gt, texts, order, ...s }) => s)
});

console.log(
  `Generated site data for ${ordered.length} samples and ${models.length} models in ${outDir}`
);
