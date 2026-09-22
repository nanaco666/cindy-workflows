# Research and content contract

## Source hierarchy

Use sources in this order:

1. Official model, release, and pricing documentation.
2. Official repository or model card.
3. A user-supplied announcement or screenshot when its origin is clear.
4. The configured Cindy catalog, only to verify local availability and current price.

Record each URL in source_notes with kind, claim_keys, and confidence. If sources disagree, keep both notes, prefer the newer first-party source, and mark the disputed field unverified until resolved.

## Facts schema

The input JSON must contain slug, as_of, topic, highlight_model, source_notes, models, cn, and en. Each model has id, name, claims, and claim_status. Prices use the same unit across all compared models.

Example shape:

{
  "slug": "glm-5-3-series-20260922",
  "as_of": "2026-09-22",
  "topic": "GLM 5.3 series",
  "highlight_model": "glm-5.3-flashx",
  "hero_image": "",
  "source_notes": [{"url": "https://example.com/official-doc", "kind": "official", "claim_keys": ["glm-5.3-flashx.price"], "confidence": "verified"}],
  "models": [{
    "id": "glm-5.3-flashx",
    "name": "GLM 5.3 FlashX",
    "badge": "NEW",
    "claims": {"modality": "text + image + video", "speed": "200 tokens/s"},
    "context_tokens": 1048576,
    "input_price_per_million": 0.37,
    "output_price_per_million": 1.25,
    "price_unit": "USD / 1M tokens",
    "claim_status": {"modality": "verified", "speed": "verified"}
  }],
  "cn": {"title": "", "lead": "", "highlights": [], "social": ""},
  "en": {"title": "", "lead": "", "highlights": [], "social": ""}
}

Use null or a dash for unavailable values. Do not use placeholder values in a finished facts file. URLs may be public; credentials and private URLs are forbidden.

## Visual contract

The renderer uses a 1080px-wide editorial poster with a dark neutral background, a highlighted model column, a comparison table, price bars when comparable, a compact source footer, and an optional hero image. It is not tied to Cindy's daily release character or a local background pack, so another operator can reproduce it with their own licensed asset or with no image.
