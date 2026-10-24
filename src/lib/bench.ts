import { asset } from '$app/paths';
import type { AssetPath } from '$app/types';

export type Thinking = 'low' | 'high' | 'thinking' | 'no thinking' | 'multi-step' | null;

export interface Model {
  label: string;
  slug: string;
  provider: string;
  openWeights: boolean;
  thinking: Thinking;
  cer: number | null;
  wer: number | null;
  read: number;
  failed: number;
  cost: number;
  latency: number;
  outTokens: number;
}

export interface Result {
  cer: number | null;
  wer: number | null;
  cost: number | null;
  latency: number | null;
  outTokens: number | null;
  error: string | null;
}

export interface Sample {
  id: string;
  group: string;
  label: string;
  ms: string;
  folio: string;
  passage: string;
  microfilm: boolean;
  lectionary: boolean;
  side: 'verso' | 'recto' | null;
  image: string;
  chars: number | null;
  results: Record<string, Result>;
}

export interface Summary {
  name: string;
  timestamp: string;
  groups: string[];
  models: Model[];
  samples: Sample[];
}

export interface Folio {
  id: string;
  gt: string;
  texts: Record<string, string>;
}

export type Cell = { kind: 'none' } | { kind: 'abs'; why: string } | { kind: 'ok'; v: number };

export interface Stats {
  mark: number | null;
  colour: number | null;
  micro: number | null;
  cer: number | null;
  wer: number | null;
}

export interface Row {
  i: number;
  m: Model;
  res: (Result | undefined)[];
  cells: Cell[];
  sat: number;
  absent: number;
  attempted: number;
  std: Stats;
  zero: Stats;
}

export const PROVIDERS = ['Anthropic', 'OpenAI', 'Google', 'OpenRouter'];
export const FAMILIES = [...PROVIDERS, 'Open weight'];
export const family = (m: Model) => (m.openWeights ? 'Open weight' : m.provider);
export const familyColor = (f: string) => `var(--fam-${f.toLowerCase().replace(' ', '-')})`;

const THINK: Record<string, string> = {
  low: 'low thinking',
  high: 'high thinking',
  thinking: 'thinking on',
  'no thinking': 'thinking off',
  'multi-step': 'low-thinking draft, medium-thinking checks'
};
export function reason(err: string | null | undefined): string {
  let m = err?.match(/hard timeout of (\d+)\s*s/i);
  if (m) return `timed out after ${m[1]} s`;
  m = err?.match(/token limit \((\d+)\)/i);
  if (m) return `ran out of tokens at the ${Number(m[1]).toLocaleString('en')} limit`;
  return 'request error';
}

export function markOf(r: Result | undefined): Cell {
  if (!r) return { kind: 'none' };
  if (r.error || r.cer == null) return { kind: 'abs', why: reason(r.error) };
  return { kind: 'ok', v: Math.max(0, Math.floor(Math.round((100 - r.cer * 100) * 1e6) / 1e6)) };
}

export const mean = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);

export function median(a: number[]): number | null {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const k = s.length >> 1;
  return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2;
}

export const fmt1 = (v: number | null) => (v == null ? '–' : (Math.round(v * 10) / 10).toFixed(1));
export const fmt0 = (v: number | null) => (v == null ? '–' : String(Math.round(v)));
export const pct = (c: number | null) => (c == null ? '–' : (c * 100).toFixed(1) + '%');

export function fmtCost(c: number | null | undefined): string {
  if (!c || c <= 0) return 'no cost recorded';
  if (c < 0.01) return '$' + c.toFixed(4);
  if (c < 0.1) return '$' + c.toFixed(3);
  return '$' + c.toFixed(2);
}

export function fmtTime(s: number | null | undefined, long = false): string {
  if (s == null) return '–';
  if (s < 90) {
    const v = Math.round(s);
    return long ? `${v} seconds` : `${v} s`;
  }
  const m = s / 60;
  if (m < 60) {
    const v = m < 10 ? Math.round(m * 10) / 10 : Math.round(m);
    return long ? `${v} minutes` : `${v} min`;
  }
  const h = Math.floor(m / 60);
  const r = Math.round(m % 60);
  return long ? `${h} hour${h > 1 ? 's' : ''}${r ? ` ${r} minutes` : ''}` : `${h} h ${r} min`;
}

export const passage = (s: Sample) => s.passage.replace(/^Rom\b/, 'Romans');
export const paperName = (s: Sample) => [s.ms, s.folio, passage(s)].filter(Boolean).join(', ');
export const who = (m: Model) =>
  `${m.provider}, ${(m.thinking && THINK[m.thinking]) ?? 'default settings'}`;

export function buildRows(summary: Summary): Row[] {
  const S = summary.samples;
  return summary.models.map((m, i) => {
    const res = S.map((s) => s.results[m.label]);
    const cells = res.map(markOf);
    const stat = (zero: boolean): Stats => {
      const marks: number[] = [];
      const colour: number[] = [];
      const micro: number[] = [];
      const cer: number[] = [];
      const wer: number[] = [];
      cells.forEach((c, p) => {
        const bucket = S[p].microfilm ? micro : colour;
        if (c.kind === 'ok') {
          marks.push(c.v);
          bucket.push(c.v);
          cer.push(res[p]!.cer!);
          wer.push(res[p]!.wer!);
        } else if (zero && c.kind === 'abs') {
          marks.push(0);
          bucket.push(0);
          cer.push(1);
          wer.push(1);
        }
      });
      return {
        mark: mean(marks),
        colour: mean(colour),
        micro: mean(micro),
        cer: mean(cer),
        wer: mean(wer)
      };
    };
    const sat = cells.filter((c) => c.kind === 'ok').length;
    const absent = cells.filter((c) => c.kind === 'abs').length;
    return {
      i,
      m,
      res,
      cells,
      sat,
      absent,
      attempted: sat + absent,
      std: stat(false),
      zero: stat(true)
    };
  });
}

export function rank(rows: Row[], zero: boolean) {
  const key = (r: Row) => (zero ? r.zero : r.std).mark;
  const order = [...rows].sort(
    (a, b) => (key(b) ?? -1) - (key(a) ?? -1) || a.m.label.localeCompare(b.m.label)
  );
  const pos = new Map<number, number | null>();
  const count = new Map<number, number>();
  let prev: number | null = null;
  let prevPos = 0;
  order.forEach((r, k) => {
    const v = key(r);
    if (v == null) return pos.set(r.i, null);
    const rounded = Math.round(v * 10);
    if (rounded !== prev) prevPos = k + 1;
    prev = rounded;
    pos.set(r.i, prevPos);
    count.set(prevPos, (count.get(prevPos) ?? 0) + 1);
  });
  const label = (i: number) => {
    const n = pos.get(i);
    return n == null ? '–' : ((count.get(n) ?? 0) > 1 ? '=' : '') + n;
  };
  return { order, pos, label };
}

export function scriptHash(row: Row, paper: number) {
  return `#${row.m.slug}.${paper + 1}`;
}

const folios = new Map<string, Promise<Folio>>();

export function loadFolio(id: string): Promise<Folio> {
  if (!folios.has(id)) {
    folios.set(
      id,
      fetch(asset(`site-data/folio/${id}.json` as AssetPath)).then((r) => {
        if (!r.ok) throw new Error(`Folio ${id} returned ${r.status}`);
        return r.json();
      })
    );
  }
  return folios.get(id)!;
}

export const store = {
  get<T>(key: string): T | null {
    try {
      return JSON.parse(localStorage.getItem(key) || 'null');
    } catch {
      return null;
    }
  },
  set(key: string, value: unknown) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      return;
    }
  }
};
