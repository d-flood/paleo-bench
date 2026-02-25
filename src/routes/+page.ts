import { asset } from '$app/paths';
import type { PageLoad } from './$types';
import type { SiteSummaryData } from '$lib/types';

export const load: PageLoad = async ({ fetch }) => {
  const response = await fetch(asset('/site-data/summary.json'));
  if (!response.ok) {
    throw new Error('Failed to load summary site data');
  }

  return { siteSummary: (await response.json()) as SiteSummaryData };
};
