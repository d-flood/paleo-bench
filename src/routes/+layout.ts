import { asset } from '$app/paths';
import type { Summary } from '#lib/bench.js';
import type { LayoutLoad } from './$types';

export const prerender = true;

export const load: LayoutLoad = async ({ fetch }) => {
  const response = await fetch(asset('site-data/summary.json'));
  if (!response.ok) throw new Error('Failed to load the benchmark summary');
  return { summary: (await response.json()) as Summary };
};
