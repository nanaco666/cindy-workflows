#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const skillDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const skill = fs.readFileSync(path.join(skillDir, 'SKILL.md'), 'utf8');
const runtime = fs.readFileSync(path.join(skillDir, 'references', 'runtime-workflow.md'), 'utf8');
const policy = fs.readFileSync(path.join(skillDir, 'references', 'domain-policy.md'), 'utf8');

for (const phrase of [
  'Never turn a one-line report into a thin, template-only Issue',
  'check whether the capability already exists',
  'test plausible causes',
]) {
  assert.ok(skill.includes(phrase), `SKILL.md missing contract: ${phrase}`);
}

for (const phrase of [
  'run the self-diagnosis pass',
  'Do not use source brevity as a shortcut',
  'what each check ruled in or out',
]) {
  assert.ok(runtime.includes(phrase), `runtime-workflow.md missing gate: ${phrase}`);
}

for (const phrase of [
  '## 6. Self-diagnosis before registration',
  '自主排查（检查项、证据、排除/保留结果）',
  '待用户补充（没有则明确“无需”',
  '`不阻塞排查`',
  '`阻塞进一步定位`',
  'Generic speculation without a check is not diagnosis',
]) {
  assert.ok(policy.includes(phrase), `domain-policy.md missing rule: ${phrase}`);
}

assert.ok(
  policy.includes('do not open a Feature Issue merely because the reporter did not find it'),
  'existing capability must not be misclassified as a feature',
);
assert.ok(
  policy.includes('Ask no more than three precise questions'),
  'reporter questions must remain bounded',
);

console.log(JSON.stringify({
  ok: true,
  cases: [
    'short-report-self-diagnosis',
    'existing-capability-check',
    'evidence-backed-hypotheses',
    'bounded-reporter-questions',
    'blocking-status',
  ],
}));
