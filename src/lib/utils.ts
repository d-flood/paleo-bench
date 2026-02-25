import { diffChars } from 'diff';

/** Format a number as a percentage string */
export function pct(n: number, decimals = 1): string {
  return (n * 100).toFixed(decimals) + '%';
}

/** Format seconds to a readable duration */
export function duration(seconds: number): string {
  if (seconds < 60) return seconds.toFixed(1) + 's';
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(0);
  return `${m}m ${s}s`;
}

/** Format cost in USD */
export function cost(n: number): string {
  return '$' + n.toFixed(4);
}

/** Format a number with commas */
export function comma(n: number): string {
  return n.toLocaleString();
}

/** Format ISO timestamp to readable date */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/** Clamp a CER/WER value for display (cap at 1.0 for gauges) */
export function clampScore(n: number): number {
  return Math.min(n, 1);
}

/** Convert CER to accuracy-like score (lower CER = better) */
export function cerToAccuracy(cer: number): number {
  return Math.max(0, 1 - cer);
}

/** Strip diacritics/punctuation and normalize whitespace for comparison/display */
export function stripDiacritics(text: string): string {
  return (
    text
      .normalize('NFD')
      .replace(/\p{M}/gu, '')
      .replace(/\p{P}/gu, '')
      .replace(/[^\S\r\n]+/g, ' ')
      // Ignore trailing spaces/tabs at line ends and EOF while preserving newlines.
      .replace(/[ \t]+(?=\r?\n|$)/g, '')
      .normalize('NFC')
  );
}

/**
 * Simple character-level diff between two strings.
 * Returns arrays of segments with match/mismatch info.
 */
export interface DiffSegment {
  text: string;
  type: 'match' | 'insert' | 'delete' | 'replace';
}

export function simpleDiff(
  reference: string,
  hypothesis: string
): { ref: DiffSegment[]; hyp: DiffSegment[] } {
  const refSegs: DiffSegment[] = [];
  const hypSegs: DiffSegment[] = [];
  function pushSeg(target: DiffSegment[], text: string, type: DiffSegment['type']) {
    if (!text) return;
    const last = target[target.length - 1];
    if (last && last.type === type) {
      last.text += text;
      return;
    }
    target.push({ text, type });
  }

  let pendingRemoved = '';
  for (const part of diffChars(reference, hypothesis)) {
    if (part.removed) {
      pendingRemoved += part.value;
      continue;
    }

    if (part.added) {
      if (pendingRemoved) {
        pushSeg(refSegs, pendingRemoved, 'replace');
        pushSeg(hypSegs, part.value, 'replace');
        pendingRemoved = '';
      } else {
        pushSeg(hypSegs, part.value, 'insert');
      }
      continue;
    }

    if (pendingRemoved) {
      pushSeg(refSegs, pendingRemoved, 'delete');
      pendingRemoved = '';
    }
    pushSeg(refSegs, part.value, 'match');
    pushSeg(hypSegs, part.value, 'match');
  }

  if (pendingRemoved) {
    pushSeg(refSegs, pendingRemoved, 'delete');
  }

  return { ref: refSegs, hyp: hypSegs };
}
