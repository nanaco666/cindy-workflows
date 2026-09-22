---
name: model-comparison-poster
description: Research AI model updates from configured authoritative URLs, verify pricing and capabilities against evidence, create bilingual comparison facts and social copy, render editable HTML posters, and optionally capture PNGs with local Chrome. Use when the user asks for a model comparison, model launch/update poster, pricing/spec table, or a repeatable research-to-image package.
---

# Model comparison poster

This workflow turns a model-update request into a reproducible evidence package, not a one-off image. It produces a facts file, Chinese and English copy, editable HTML, and optional Chrome screenshots. It never assumes the operator's local paths, credentials, catalog state, or asset library.

Read references/research-and-content.md before researching or editing facts. Use the installed workflow directory and its config.local.json; paths in the template are placeholders and must be completed by the operator.

## Required workflow

1. Read config.local.json. Resolve asset_dir, source_urls, and optional catalog_url from that file or explicit environment variables. Never copy a path from another machine.
2. Research the requested model family. Prefer first-party model cards, pricing pages, release announcements, and the user's explicitly supplied URLs. Use the configured Cindy catalog only as a price/availability cross-check, not as proof of model capabilities.
3. Build content/<slug>.json using the schema in references/research-and-content.md. Every material claim needs a source URL and a confidence of verified or unverified; do not fill missing values from memory.
4. Separate facts from editorial copy. Keep source_notes as the audit layer, then write concise cn and en titles, lead, table labels, highlights, and social posts. English must contain no untranslated CJK text.
5. Run: python3 scripts/validate_facts.py content/<slug>.json --config config.local.json. Fix every error before rendering.
6. Run: python3 scripts/render.py content/<slug>.json --config config.local.json --out-dir out/<slug>. This creates self-contained index.html and index-en.html.
7. If Chrome and Playwright are available, run scripts/capture_poster.py for both HTML files. If capture prerequisites are missing, keep the HTML deliverable and report the exact configuration needed; do not switch to an image model.
8. Inspect both language outputs for clipping, bad contrast, wrong prices, duplicate claims, CJK leakage in English, and table readability. Record any unresolved item in the run report.

## Editorial rules

- Make the newly released or most useful model the highlighted column; compare only models in the same family or clearly label the comparison scope.
- Use real proportional price bars only when all compared prices are verified and use the same units. If a price is unknown, show a dash and omit the bar comparison.
- Preserve unverified facts in source_notes; never turn an unknown parameter count, modality, speed, or plan entitlement into a definitive sentence.
- Chinese copy begins with a descriptive title and a user scenario. English copy follows: launch sentence, 3–6 short highlights, complete comparison metrics, and source links.
- Do not include private repository links, local absolute paths, tokens, customer data, or internal implementation terms in the output.
- Use user-supplied or configured image resources only. The renderer accepts a local image path from hero_image; it does not download arbitrary images or generate a replacement.

## Output

The final handoff should list the facts JSON, both HTML files, any PNGs, source URLs, unresolved facts, and the exact command needed to rerun the package.
