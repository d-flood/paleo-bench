import { dev } from '$app/environment';
import { base } from '$app/paths';
import type { BenchmarkData } from '$lib/types';

const RESULTS_FILENAME = 'results.json';
const VERSION_FILENAME = 'results.version.json';
const RESULTS_PATH = `${base}/${RESULTS_FILENAME}`;
const VERSION_PATH = `${base}/${VERSION_FILENAME}`;

type VersionPayload = {
  version?: string;
};

function buildDevResultsUrl(): string {
  return `${RESULTS_PATH}?t=${Date.now()}`;
}

async function fetchResults(
  fetchFn: typeof fetch,
  url: string,
  options?: RequestInit
): Promise<BenchmarkData | null> {
  const response = await fetchFn(url, options);
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as BenchmarkData;
}

async function fetchVersion(fetchFn: typeof fetch): Promise<string | null> {
  try {
    const response = await fetchFn(VERSION_PATH);
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as VersionPayload;
    return payload.version ?? null;
  } catch {
    return null;
  }
}

export async function loadBenchmarkData(fetchFn: typeof fetch): Promise<BenchmarkData> {
  if (dev) {
    const data = await fetchResults(fetchFn, buildDevResultsUrl(), { cache: 'no-store' });
    if (!data) {
      throw new Error(`Failed to load ${RESULTS_PATH}`);
    }
    return data;
  }

  const version = await fetchVersion(fetchFn);
  const candidateUrls = version
    ? [`${RESULTS_PATH}?v=${encodeURIComponent(version)}`, RESULTS_PATH]
    : [RESULTS_PATH];

  for (const url of candidateUrls) {
    const data = await fetchResults(fetchFn, url);
    if (data) {
      return data;
    }
  }

  throw new Error(`Failed to load ${RESULTS_PATH}`);
}
