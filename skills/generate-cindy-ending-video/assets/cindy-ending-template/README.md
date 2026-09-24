# Cindy Summary + Ending Builder

This folder contains the reusable HTML editor and MP4 renderer bundled with the `generate-cindy-ending-video` Skill.

## Requirements

- Node.js 22 or newer
- Google Chrome or Chromium
- ffmpeg and ffprobe with H.264/AAC support

Run:

```bash
node scripts/preflight.mjs
```

If an executable is not discoverable, set `CHROME_BIN`, `FFMPEG`, or `FFPROBE`.

## Preview

Open `index.html`, or build a self-contained copy:

```bash
node scripts/build-single-file.mjs ./cindy-ending-preview.html
```

The editor stores changes in localStorage and can export/import JSON. It does not export MP4 directly.

## Render

```bash
node scripts/render-video.mjs \
  --input /absolute/path/source.mp4 \
  --config ./config.example.json \
  --locale zh \
  --output ./renders/final-zh.mp4
```

Omit `--input` for a standalone Summary + Ending clip. Default output is 1920×1080, 30fps, H.264/AAC. Summary defaults to 3.5 seconds and Ending to 2 seconds.

The renderer captures the actual HTML/CSS frame-by-frame through Chrome DevTools, then uses ffmpeg for audio and MP4 composition. This keeps rendered typography and motion aligned with the browser preview.

## Bundled assets

- `assets/brand/cindy-white.png`: Cindy logo
- `assets/brand/Anton-Latin.woff2`: English Summary display font
- `assets/brand/BebasNeue-Regular.ttf`: legacy/game display font
- `assets/audio/*.wav`: row, logo, switch, and Arcade sounds

Font license texts are stored beside the fonts. Cindy brand assets remain subject to the brand owner’s terms.
