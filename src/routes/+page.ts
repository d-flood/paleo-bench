import type { PageLoad } from './$types';
import { loadBenchmarkData } from '$lib/results-loader';

export const load: PageLoad = async ({ fetch }) => {
  return { benchmarkData: await loadBenchmarkData(fetch) };
};
