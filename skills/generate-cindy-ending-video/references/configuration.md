# Configuration

```json
{
  "version": 1,
  "copy": {
    "zh": ["本地运行，数据更可控", "自选模型，使用更灵活", "Ollama 已接入 Cindy"],
    "en": ["Run locally. Keep control.", "Choose the model that fits.", "Ollama is now in Cindy."]
  },
  "ending": {
    "color": "#F70121",
    "animation": "center-wipe"
  },
  "timing": {
    "summaryMs": 3500,
    "endingMs": 2000
  }
}
```

Rules:

- `copy.zh` and `copy.en`: 1–4 strings each, at most 30 characters per string.
- `ending.color`: six-digit hexadecimal color.
- `ending.animation`: `center-wipe`, `fade-scale`, `slide-up`, or `arcade-clear`.
- Summary and Ending total 5.5 seconds. Summary may be 1.5–3.5 seconds; Ending remains at least 2 seconds.
- `center-wipe` is the standard Cindy close. Its HTML animation expands vertically from the center, then reveals the logo with the bundled spring timing.
