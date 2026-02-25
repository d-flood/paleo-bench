import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const resultsPath = resolve(process.cwd(), 'static/results.json');
const versionPath = resolve(process.cwd(), 'static/results.version.json');

let resultsBuffer;
try {
  resultsBuffer = readFileSync(resultsPath);
} catch (error) {
  console.error(`Failed to read ${resultsPath}:`, error);
  process.exit(1);
}

const version = createHash('sha256').update(resultsBuffer).digest('hex').slice(0, 12);
const payload = `${JSON.stringify({ version }, null, 2)}\n`;

try {
  writeFileSync(versionPath, payload, 'utf-8');
} catch (error) {
  console.error(`Failed to write ${versionPath}:`, error);
  process.exit(1);
}

console.log(`Wrote static/results.version.json (v=${version})`);
