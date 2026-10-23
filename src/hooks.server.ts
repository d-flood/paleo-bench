import type { Handle } from '@sveltejs/kit/hooks';

const COMMON = [
  'alegreya-latin-wght-normal',
  'alegreya-sans-latin-400-normal',
  'alegreya-sans-latin-500-normal'
];
const MARKED = ['alegreya-latin-wght-italic', 'alegreya-sans-latin-700-normal'];
const ROUTE_FONTS: Record<string, string[]> = {
  '/by-folio': MARKED,
  '/transcriptions': [...MARKED, 'alegreya-greek-wght-normal', 'alegreya-greek-wght-italic']
};

export const handle: Handle = ({ event, resolve }) => {
  const fonts = new Set([...COMMON, ...(ROUTE_FONTS[event.route.id ?? ''] ?? [])]);
  return resolve(event, {
    preload: (input) =>
      input.type === 'font'
        ? fonts.has(/([\w-]+)\.woff2$/.exec(input.filename)?.[1] ?? '')
        : input.type === 'css'
  });
};
