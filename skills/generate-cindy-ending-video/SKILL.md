---
name: generate-cindy-ending-video
description: Generate a concise Chinese or English Cindy feature-summary page and fixed brand Ending, optionally append both to an existing video, and render a validated 1920×1080 H.264/AAC MP4. Use for Cindy 功能介绍视频结尾、总结页、片尾、Ending, or reusable Cindy video closes; not for editing the main demo footage.
---

# Generate Cindy Ending Video

Use the bundled template in `assets/cindy-ending-template/`. The HTML/CSS is the only source of truth for Summary typography, layout, and animation. Never recreate the Summary as a static image or in another layout system.

## Workflow

1. If the user provides a source video, inspect its duration, dimensions, frame rate, codecs, and final seconds. Do not append a duplicate close.
2. Write no more than four concise summary lines per language, each at most 30 characters. State user value, not merely the feature label. Write Chinese and English independently rather than translating mechanically.
3. Put the approved copy, Ending style, and timing in the JSON shape documented in [references/configuration.md](references/configuration.md). Default to `center-wipe`, Summary 3.5 seconds, and Ending 2 seconds.
4. For visual review, build the self-contained editor and open it in local Chrome:

   ```bash
   cd assets/cindy-ending-template
   node scripts/build-single-file.mjs /absolute/path/cindy-ending-preview.html
   ```

5. Before rendering, run `node assets/cindy-ending-template/scripts/preflight.mjs`. The renderer needs Node.js 22+, Chrome or Chromium, ffmpeg, and ffprobe. Custom executable paths may be set with `CHROME_BIN`, `FFMPEG`, and `FFPROBE`.
6. Render the requested locale:

   ```bash
   node assets/cindy-ending-template/scripts/render-video.mjs \
     --input /absolute/path/source.mp4 \
     --config /absolute/path/config.json \
     --locale zh \
     --output /absolute/path/final-zh.mp4
   ```

   Omit `--input` to generate only the Summary + Ending clip. Run once with `--locale zh` and once with `--locale en` when both outputs are requested.
7. Validate with ffprobe. The default contract is 1920×1080, 30fps, H.264 video, AAC audio, Summary 3.5 seconds, and Ending 2 seconds.

## Invariants

- Render both Summary and Ending frame-by-frame from the actual HTML/CSS in Chrome. A browser screen recording, ffmpeg `drawtext`, or a separately maintained Swift/AppKit layout is not an acceptable substitute.
- Preserve the bundled Cindy logo, font assets, `logo.wav`, restrained row-click sounds, and fixed standard red treatment unless the user explicitly changes the configurable Ending color.
- Use `arcade-clear` only when the user asks for a game-like close. Keep `center-wipe`, `fade-scale`, and `slide-up` available.
- Do not add unsupported claims, URLs, credits, slogans, or an extra CTA page.
- Never overwrite the source video. Write to a new output path.
- If the HTML cannot be rendered faithfully in the available environment, report the missing dependency instead of exporting an approximation.

## Assets and redistribution

The Skill includes the HTML/CSS/JS template, Cindy logo, fonts, sounds, example config, and deterministic render scripts. Font license texts are stored beside the font files. Cindy brand assets remain subject to their owner’s brand terms even when the surrounding repository is MIT-licensed.
