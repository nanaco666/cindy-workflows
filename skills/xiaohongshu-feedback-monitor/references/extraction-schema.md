# Extraction schemas

## Raw record

```json
{
  "account": "primary",
  "source": "comment",
  "user": "display name",
  "time_raw": "昨天 16:46",
  "content": "user-authored text",
  "quote": "optional surrounding text",
  "interaction_type": "评论了你的笔记",
  "url": "optional stable URL",
  "conversation_id": "optional private-message conversation id",
  "side": "other"
}
```

Required fields are `source`, `user`, `time_raw`, and `content`. `source` is `comment` or `dm`.

## Normalized record

The normalizer adds:

```json
{
  "account": "primary",
  "source": "comment",
  "user": "display name",
  "time_raw": "昨天 16:46",
  "timestamp": "2026-08-13T16:46:00+08:00",
  "date": "2026-08-13",
  "content": "user-authored text",
  "quote": "optional surrounding text",
  "interaction_type": "评论了你的笔记",
  "url": "optional stable URL",
  "conversation_id": "",
  "side": "other",
  "fingerprint": "sha256 prefix"
}
```

## State file

```json
{
  "version": 1,
  "accounts": {
    "primary": {
      "last_success_at": null,
      "cursor_start": null,
      "fingerprints": {
        "fingerprint-value": "2026-08-18T09:00:00+08:00"
      }
    }
  }
}
```

The update script prunes fingerprints older than 90 days by default. Do not store raw message content in `state.json`.
