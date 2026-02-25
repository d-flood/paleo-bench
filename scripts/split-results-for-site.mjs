import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';

const resultsPath = resolve(process.cwd(), 'static/results.json');
const outDir = resolve(process.cwd(), 'static/site-data');
const samplesDir = resolve(outDir, 'samples');

function stableSampleId(group, label, image) {
  const key = `${group}::${label}::${image}`;
  return createHash('sha1').update(key).digest('hex').slice(0, 12);
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
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, 'utf-8');
}

const data = readResults();
const benchmark = data.benchmark ?? {};
const modelSummaries = data.model_summaries ?? {};
const groupSummaries = data.group_summaries ?? {};
const config = benchmark.config ?? {};
const models = Array.isArray(config.models) ? config.models : [];
const results = Array.isArray(data.results) ? data.results : [];

rmSync(outDir, { recursive: true, force: true });
mkdirSync(samplesDir, { recursive: true });

const summary = {
  benchmark: {
    name: benchmark.name,
    timestamp: benchmark.timestamp,
    total_duration_seconds: benchmark.total_duration_seconds,
    config: {
      models,
      groups: Array.isArray(config.groups) ? config.groups : [],
      sample_count: config.sample_count ?? 0
    }
  },
  model_summaries: modelSummaries,
  group_summaries: groupSummaries
};

const modelOrder = models.map((m) => m.label).filter((v) => typeof v === 'string');
const qualityRankedModelOrder = [...modelOrder].sort((a, b) => {
  const aSummary = modelSummaries[a];
  const bSummary = modelSummaries[b];
  const aQuality =
    aSummary && aSummary.samples_evaluated > 0 ? 1 - Number(aSummary.cer_mean) : Number.NEGATIVE_INFINITY;
  const bQuality =
    bSummary && bSummary.samples_evaluated > 0 ? 1 - Number(bSummary.cer_mean) : Number.NEGATIVE_INFINITY;
  return bQuality - aQuality;
});

const samplesMap = new Map();
for (const row of results) {
  const group = row.group ?? '';
  const label = row.label ?? '';
  const image = row.image ?? '';
  const sampleId = stableSampleId(group, label, image);

  if (!samplesMap.has(sampleId)) {
    samplesMap.set(sampleId, {
      sampleId,
      group,
      label,
      image,
      ground_truth_file: row.ground_truth_file ?? '',
      ground_truth_text: row.ground_truth_text ?? '',
      availableModels: [],
      resultsByModel: {},
      modelOutputs: {}
    });
  }

  const sample = samplesMap.get(sampleId);
  const model = row.model ?? '';

  sample.resultsByModel[model] = {
    model,
    error: row.error ?? null,
    metrics: row.metrics ?? null,
    response_metadata: row.response_metadata ?? {
      input_tokens: 0,
      output_tokens: 0,
      cost: 0,
      latency_seconds: 0
    }
  };
  sample.modelOutputs[model] = row.model_output ?? '';
}

const compareSamples = [];
for (const sample of samplesMap.values()) {
  const present = new Set(Object.keys(sample.resultsByModel));
  sample.availableModels = [
    ...qualityRankedModelOrder.filter((model) => present.has(model)),
    ...Object.keys(sample.resultsByModel).filter((model) => !qualityRankedModelOrder.includes(model))
  ];

  compareSamples.push({
    sampleId: sample.sampleId,
    group: sample.group,
    label: sample.label,
    image: sample.image,
    ground_truth_file: sample.ground_truth_file,
    availableModels: sample.availableModels,
    resultsByModel: sample.resultsByModel
  });

  writeJson(resolve(samplesDir, `${sample.sampleId}.json`), {
    sampleId: sample.sampleId,
    ground_truth_text: sample.ground_truth_text,
    model_outputs: sample.modelOutputs
  });
}

compareSamples.sort((a, b) => {
  if (a.group !== b.group) return String(a.group).localeCompare(String(b.group));
  return String(a.label).localeCompare(String(b.label));
});

const compareIndex = {
  benchmark: {
    name: benchmark.name,
    timestamp: benchmark.timestamp,
    total_duration_seconds: benchmark.total_duration_seconds
  },
  model_summaries: modelSummaries,
  model_order: modelOrder,
  quality_ranked_model_order: qualityRankedModelOrder,
  samples: compareSamples
};

writeJson(resolve(outDir, 'summary.json'), summary);
writeJson(resolve(outDir, 'compare-index.json'), compareIndex);

console.log(`Generated site data in ${outDir}`);
