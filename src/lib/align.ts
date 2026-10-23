import { diffArrays } from 'diff';

export interface Token {
  w: string;
  k: string;
  line: number;
}

export interface Line {
  index: number;
  kind: 'text' | 'column' | 'blank';
  text: string;
  n: number | null;
}

export interface GroundTruth {
  lines: Line[];
  tokens: Token[];
}

export interface Unit {
  type: 'eq' | 'sub' | 'del' | 'ins';
  from: number;
  to: number;
  pred: string[];
  lemma: string[];
  line: number;
}

export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Mn}/gu, '')
    .replace(/\p{P}/gu, '')
    .replace(/[^\S\r\n]+/g, ' ')
    .replace(/[ \t]+(?=\r?\n|$)/g, '')
    .normalize('NFC');
}

const LOOKALIKES: Record<string, string> = {
  A: 'Α',
  B: 'Β',
  C: 'Ϲ',
  E: 'Ε',
  H: 'Η',
  I: 'Ι',
  K: 'Κ',
  M: 'Μ',
  N: 'Ν',
  O: 'Ο',
  P: 'Ρ',
  T: 'Τ',
  X: 'Χ',
  Y: 'Υ',
  Z: 'Ζ',
  a: 'α',
  c: 'ϲ',
  i: 'ι',
  k: 'κ',
  o: 'ο',
  p: 'ρ',
  u: 'υ',
  v: 'ν',
  x: 'χ',
  А: 'Α',
  В: 'Β',
  Г: 'Γ',
  Е: 'Ε',
  К: 'Κ',
  Л: 'Λ',
  М: 'Μ',
  Н: 'Η',
  О: 'Ο',
  П: 'Π',
  Р: 'Ρ',
  С: 'Ϲ',
  Т: 'Τ',
  Ф: 'Φ',
  Х: 'Χ',
  а: 'α',
  к: 'κ',
  о: 'ο',
  п: 'π',
  р: 'ρ',
  с: 'ϲ',
  т: 'τ',
  ф: 'φ',
  х: 'χ'
};
const LETTER_FORMS: Record<string, string> = { ς: 'σ', ϛ: 'στ', ȣ: 'ου', ϗ: 'και' };
const greekLetter = /[Ͱ-Ͽἀ-῿]/;

export function scoringKey(text: string): string {
  return text
    .replace(/\S+/g, (w) =>
      greekLetter.test(w) ? w.replace(/./gu, (ch) => LOOKALIKES[ch] ?? ch) : w
    )
    .replace(/[\p{Sk}\p{Lm}]/gu, '')
    .normalize('NFKD')
    .replace(/\p{Mn}/gu, '')
    .normalize('NFC')
    .toLowerCase()
    .replace(/[ςϛȣϗ]/g, (ch) => LETTER_FORMS[ch]);
}

export interface CharPart {
  type: 'eq' | 'sub' | 'extra' | 'missing';
  pred: string;
  gt: string;
}

interface KeyChar {
  d: string;
  k: string;
}

function keyChars(text: string): KeyChar[] {
  const out: KeyChar[] = [];
  for (const [seg] of text.matchAll(/\S+|\s+/g)) {
    if (/^\s/.test(seg)) {
      out.push({ d: ' ', k: ' ' });
      continue;
    }
    const greek = greekLetter.test(seg);
    for (const ch of seg) {
      const key = scoringKey(greek ? (LOOKALIKES[ch] ?? ch) : ch);
      [...key].forEach((k, i) => out.push({ d: i ? '' : ch, k }));
    }
  }
  return out;
}

export function charDiff(pred: string, gt: string): { parts: CharPart[]; similarity: number } {
  const a = keyChars(pred);
  const b = keyChars(gt);
  const text = (list: KeyChar[]) => list.map((c) => c.d).join('');
  const parts: CharPart[] = [];
  let ai = 0;
  let bi = 0;
  let same = 0;
  for (const p of diffArrays(a, b, { comparator: (x, y) => x.k === y.k })) {
    const n = p.count ?? p.value.length;
    if (p.removed) {
      parts.push({ type: 'extra', pred: text(a.slice(ai, ai + n)), gt: '' });
      ai += n;
    } else if (p.added) {
      const gtText = text(b.slice(bi, bi + n));
      bi += n;
      const last = parts.at(-1);
      if (last?.type === 'extra') {
        last.type = 'sub';
        last.gt = gtText;
      } else parts.push({ type: 'missing', pred: '', gt: gtText });
    } else {
      parts.push({ type: 'eq', pred: text(a.slice(ai, ai + n)), gt: text(b.slice(bi, bi + n)) });
      ai += n;
      bi += n;
      same += n;
    }
  }
  return { parts, similarity: same / Math.max(a.length, b.length, 1) };
}

export function parseGroundTruth(text: string): GroundTruth {
  const lines: Line[] = [];
  const tokens: Token[] = [];
  let n = 0;
  normalize(text)
    .split('\n')
    .forEach((raw, index) => {
      const trimmed = raw.trim();
      const kind = !trimmed ? 'blank' : /^Column \d+$/.test(trimmed) ? 'column' : 'text';
      lines.push({ index, kind, text: trimmed, n: kind === 'text' ? ++n : null });
      for (const w of trimmed.split(' ').filter(Boolean))
        tokens.push({ w, k: scoringKey(w), line: index });
    });
  return { lines, tokens };
}

export function align(gt: GroundTruth, output: string): Unit[] {
  const pred = normalize(output).split(/\s+/).filter(Boolean);
  const predKeys = pred.map(scoringKey);
  const gtKeys = gt.tokens.map((t) => t.k);
  const parts = diffArrays(gtKeys, predKeys, { timeout: 150 }) ?? [
    { removed: true, added: false, count: gtKeys.length, value: gtKeys },
    { added: true, removed: false, count: predKeys.length, value: predKeys }
  ];
  const units: Unit[] = [];
  let gi = 0;
  let pi = 0;
  let open: { from: number; to: number; pred: string[] } | null = null;
  const close = () => {
    if (!open) return;
    const type = open.to === open.from ? 'ins' : open.pred.length ? 'sub' : 'del';
    units.push({ type, ...open, lemma: [], line: 0 });
    open = null;
  };
  for (const p of parts) {
    const count = p.count ?? p.value.length;
    if (!p.added && !p.removed) {
      close();
      units.push({
        type: 'eq',
        from: gi,
        to: gi + count,
        pred: pred.slice(pi, pi + count),
        lemma: [],
        line: 0
      });
      gi += count;
      pi += count;
      continue;
    }
    open ??= { from: gi, to: gi, pred: [] };
    if (p.removed) {
      gi += count;
      open.to = gi;
    } else {
      open.pred.push(...pred.slice(pi, pi + count));
      pi += count;
    }
  }
  close();
  for (const u of units) {
    const anchor = u.type === 'ins' ? Math.max(0, u.from - 1) : u.from;
    u.line = gt.tokens[Math.min(anchor, gt.tokens.length - 1)]?.line ?? 0;
    u.lemma = gt.tokens.slice(u.from, u.to).map((t) => t.w);
  }
  return units;
}

function lev(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++)
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[b.length];
}

export function unitCost(u: Unit): number {
  if (u.type === 'eq') return 0;
  const a = scoringKey(u.lemma.join(' '));
  const b = scoringKey(u.pred.join(' '));
  return a.length * b.length > 4e6 ? Math.max(a.length, b.length) : lev(a, b);
}

export function lineCosts(units: Unit[]): Map<number, number> {
  const costs = new Map<number, number>();
  for (const u of units)
    if (u.type !== 'eq') costs.set(u.line, (costs.get(u.line) ?? 0) + unitCost(u));
  return costs;
}

const foreign = /[Ѐ-ӿA-Za-z]/;
const greek = /[Ͱ-Ͽἀ-῿]/;

export function foreignChars(word: string): boolean[] {
  const mixed = greek.test(word);
  return [...word].map((ch) => mixed && foreign.test(ch));
}
