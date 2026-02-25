import { asset } from '$app/paths';
import type { PageLoad } from './$types';
import type { CompareIndexData } from '$lib/types';

export const load: PageLoad = async ({ fetch }) => {
  const response = await fetch(asset('/site-data/compare-index.json'));
  if (!response.ok) {
    throw new Error('Failed to load compare site data');
  }

  return { compareIndex: (await response.json()) as CompareIndexData };
};
