---
name: cindy-update-poster
description: >
  Prepare Cindy daily release packages: verify what shipped, reconcile Release notes with the full
  merged-PR interval, edit Chinese and English copy, create an HTML/CSS poster, and capture it with
  a browser screenshot. Use for 今日更新、日报、更新图、版本号出图、release notes、社区发版文案，
  or requests to reuse and curate Cindy character artwork.
---

# Cindy daily release package

Work in the installed workflow directory, normally
`.cindy/workflows/cindy-update-poster/`. Deliver:

- one Chinese editable HTML poster and browser-captured PNG;
- one English editable HTML poster and browser-captured PNG;
- Chinese community copy with a descriptive title;
- English community copy matched to the current `@Cindy_Updates` account voice;
- the editable content JSON and HTML source.

The final task response must paste the complete Chinese and English community copy inline. A JSON path,
HTML path, or statement such as "copy has been written to the file" is not a substitute for showing the
actual publishable text.

Use a fresh date/revision filename so a mobile client cannot keep showing an older cached image. Do not
create or send an Outlook draft unless explicitly requested.

## 1. Establish what actually shipped

Run from the poster repository:

```bash
python3 collect.py <YYYY-MM-DD>
```

Only formal public Releases count. Beta, canary, prerelease, and draft releases are internal or
unfinished and must be excluded. If no formal public Cindy Release was published on that date, do not
make a poster or public copy. Calendar-day merged PRs can be recorded for audit, but are not a release
substitute.

For formal Releases, use the exact Release footer commit. The previous formal Release commit through
the current Release commit is the version interval. Every merged PR in that interval supplies the real
features, fixes, and contributor totals; Release notes only supply the public themes and story.
Same-day PRs outside the interval stay in `day_merged_prs` and must not inflate the poster totals.

Check platform claims separately:

- desktop: public Release/build evidence;
- mobile: production OTA or equivalent evidence only;
- server: production only when a `main → release` deployment PR is merged in `xindong/cindy-server`.

If uncertain, omit the claim or label it work in progress.

## 2. Organize facts and copy

Edit `content/<day_id>.json`. Preserve all verified Release themes in `editorial.source_themes` as the
audit layer. `cn.themes` and `en.themes` are selected visible copy: merge related themes and shorten
descriptions by meaning and available space without inventing facts.

Release notes are not the only visible source: when the complete release interval has fixes but the
formal Release lists `fixes: 0`, select a concise set of real, user-impacting fixes from the merged PR
interval and render them in a separate `FIXED` section. Never let a zero Release-note fix count hide
interval fixes. Keep the complete interval count in `counts`, and preserve the actual PR publisher on
each selected fix theme.

Keep theme publisher attribution separate from top-level PR-derived credits. Keep complete counts from
`counts` even when only a subset of themes is visible. Preserve newest Release order first when several
formal Releases ship on one day.

Chinese copy needs a clear descriptive title and user scenario. English copy must be fully translated,
except contributor names and exact technical identifiers.

### English community voice

Before drafting, read and compare several recent release posts from `https://x.com/Cindy_Updates`.
Use the account's current wording and rhythm, not a remembered generic template. The English post should
keep this established structure (adapt the number of highlights to the actual Release; do not copy facts
from the example):

```text
Cindy v0.1.28 is out 🚀

🧩 Plugins, reorganized
@ One search for tabs, windows, tasks & files
↩️ Invisible Git savepoints
📱 HTML preview on mobile
🤖 Better subagents
💬 Full Telegram streams

17 features · 48 fixes · 24 contributors
https://github.com/makecindy/cindy/releases/tag/v0.1.28
```

Replace the version, highlights, complete interval totals, and Release URL with verified current data.
Keep the short emoji-led fragments and the compact metric line; do not add hashtags or a contributor
roll call by default. Chinese community copy is a separate adaptation and must begin with a clear title,
then a short user-scenario lead, selected feature/fix highlights, complete interval totals, and the exact
Release URL.

## 3. Use approved local assets

The active manifest is `assets/pose-library.json`; only enabled entries in `assets/poses/` are approved.
Choose a stable reference with `pose_library.py` by `day_id`. Do not generate a new character for a daily
poster. Use approved character artwork directly in the HTML and preserve face, proportions, navy bob,
amber eyes, blue/red rim light, ivory cardigan, pale-blue dress, single silver geometric chevron earring
on anatomical left ear, and black cat details. The active daily library uses white slouch socks and
dark-brown chunky loafers.

The official Cindy wordmark is a permanent local asset and must be embedded directly in HTML. The
installed workflow provides it relative to its own directory:

```text
assets/brand/std-white.png
```

SHA-256:
`7ae927c07f7334e337e8f7c9217f8133a8d009032b2f653616528173e4cc9e4b`

Before HTML generation, verify file existence and checksum. Do not search the web, download a replacement,
inspect old posters for a logo, ask imagegen to redraw it, typeset a lookalike, recolor it, crop it, or add
another Cindy mark. If the checksum fails, stop and report the local asset problem.

The pure-background library is a local pool configured by the installer/user:

```text
<background_dir>/
```

Set `background_dir` in `config.local.json` or `CINDY_POSTER_BACKGROUND_DIR` to the pool root. For every
new run, randomly choose one source image from `01-used-backgrounds/` or `02-historical-variants/`.
Never use the `00-index/` preview thumbnails as poster art, and do not hard-code the previous day's
background. Do not generate a replacement background with ImageGen. An explicit
`visual.background_path` may pin a specific image only when the user deliberately requests one. Embed the
selected source image into both language HTML files and print its path in the run output. If the pool is
missing or empty, stop with a clear configuration error rather than silently falling back to a fixed pose.

## 4. HTML first, browser screenshot second

The daily poster path is deterministic and must not call GPT imagegen:

```bash
python3 poster.py content/<day_id>.json
```

The command runs `html_poster.py` and `capture_poster.py`, producing:

- `out/html/<day_id>-cn.html` and `out/html/<day_id>-en.html` — editable HTML/CSS;
- `out/posters/cindy-daily-<day_id>-html-cn.png` and `...-en.png` — Chrome screenshots.

Treat the poster as a branded web page, not a dashboard. The composition has three layers:

1. a full-bleed, cinematic Cindy/game-key-art background, aligned from the top downward so the
   character's head and face are not lost to centered cropping;
2. a 40–50% black translucent veil, with a stronger left-to-right gradient where copy sits;
3. the established release text modules, rebuilt in HTML/CSS and kept in the same visual positions as the
   approved reference posters.

Keep the reusable brand shell stable across runs: the thin frame, corner geometry, Cindy wordmark,
patch-dossier masthead, barcode/date treatment, red hatch and update badge, footer rules, version/URL
line, and restrained red-blue lighting. The task-specific content layer only replaces the release title,
version/date, lead, feature/fix summaries, complete interval metrics, and contributor line. Use long
editorial rows with numbered markers, platform/type metadata, descriptions, red edge accents and clipped
corner details; do not turn the content into rounded cards, equal dashboard tiles, stat widgets, or an
empty module. Make the background and character carry the visual weight while the black veil keeps all
copy readable without covering the face, eyes, hands, earring, prop, or cat.

HTML/CSS controls the composition, exact text, metrics, local Logo, selected pool background, dark
game-like treatment, red geometric accents, and typography. Chrome captures a 1240px-wide page; the
document has no minimum or maximum height and grows vertically with the rendered copy. Background `cover`
positioning must use a top anchor (`object-position: center top`) so the character's head and face are not
lost to centered cropping.
Do not call `gpt-image-2`, another image model, `brief.py`, or legacy Pillow merely to make the daily
poster. `brief.py` and `--legacy-render` are compatibility/debug paths only.

Keep the established Cindy visual language: dark navy/near-black foundation, restrained Cindy-red geometry,
cool game-key-art attitude, editorial condensed typography, a strong figure anchor, and readable negative
space. Vary the art position and safe copy area only when the selected approved pose requires it; do not
invent a generic dashboard or empty modules.

## 5. Validate

Inspect both HTML and screenshots:

- formal Release version, date, URL, lead theme and selected themes;
- complete shipped-interval `features / fixes / contributors`;
- no Beta/canary treated as a public release;
- Chinese/English separation and no CJK leakage in English;
- no placeholder, fake metric, clipping, unreadable text, or overlap;
- exact local wordmark present and unaltered;
- approved character, one correct earring, and cat details;
- text does not cover face, eyes, hands, earring, prop, or cat;
- PNG width is 1240px, the height is the actual rendered document height (never forced to 1754px), and
the capture came from Chrome.

Run:

```bash
python3 -m py_compile brief.py poster.py collect.py pose_library.py html_poster.py capture_poster.py
python3 poster.py content/<day_id>.json --html-only
python3 poster.py content/<day_id>.json
```

If screenshot capture fails, fix the local HTML/CSS or Chrome command. Do not switch to GPT imagegen as
an automatic fallback. Image generation is allowed only when the user explicitly requests a new visual
asset or character pose, with approved reference conditioning.

## Stop conditions

Stop before delivery when there is no formal Release, the Release interval or counts are unresolved, a
mobile/server claim lacks production evidence, English is untranslated, assets are unapproved, the Logo
checksum fails, or the HTML/screenshot contains fake copy, empty filler, clipping, or focal overlap.

## Scheduled-task rule

The scheduled task must first collect the formal Release, edit the JSON, generate HTML, and capture PNGs.
It must never begin with GPT imagegen. Beta/canary/prerelease versions are always excluded from the
public daily package.
