#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const pairs = [
  [
    path.join(root, 'templates', 'config', 'support-policy.example.json'),
    path.join(root, 'skills', 'filo-support-replies', 'assets', 'support-policy.example.json'),
  ],
  [
    path.join(root, 'templates', 'config', 'feedback-triage.example.json'),
    path.join(root, 'skills', 'filoai-feedback-triage', 'assets', 'config.example.json'),
  ],
];
for (const [left, right] of pairs) {
  const a = JSON.stringify(JSON.parse(fs.readFileSync(left, 'utf8')));
  const b = JSON.stringify(JSON.parse(fs.readFileSync(right, 'utf8')));
  if (a !== b) {
    console.error(`TEMPLATE SYNC FAILED: ${path.relative(root, left)} != ${path.relative(root, right)}`);
    process.exit(1);
  }
}
console.log('TEMPLATE SYNC PASSED');
