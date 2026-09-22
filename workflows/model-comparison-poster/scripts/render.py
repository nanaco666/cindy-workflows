#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
from pathlib import Path

def image_data(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return "data:{};base64,{}".format(mime, base64.b64encode(path.read_bytes()).decode())

def price(value: object) -> str:
    return "—" if value is None else "${:g}".format(value)

def page(data: dict, language: str, hero: str) -> str:
    block = data[language]
    models = data["models"]
    rows = [
        ("Context", "上下文", lambda m: "{:}".format(m.get("context_tokens", 0)) if m.get("context_tokens") else "—"),
        ("Modality", "模态", lambda m: m.get("claims", {}).get("modality", "—")),
        ("Speed", "速度", lambda m: m.get("claims", {}).get("speed", "—")),
        ("Input / 1M", "输入 / 1M", lambda m: price(m.get("input_price_per_million"))),
        ("Output / 1M", "输出 / 1M", lambda m: price(m.get("output_price_per_million"))),
    ]
    headers = "".join("<th class='{}'>{}<small>{}</small></th>".format("hot" if m["id"] == data["highlight_model"] else "", html.escape(m["name"]), html.escape(str(m.get("badge") or ""))) for m in models)
    row_html = []
    for en_label, cn_label, getter in rows:
        label = en_label if language == "en" else cn_label
        cells = "".join("<td class='{}'>{}</td>".format("hot" if m["id"] == data["highlight_model"] else "", html.escape(str(getter(m)))) for m in models)
        row_html.append("<tr><th>{}</th>{}</tr>".format(html.escape(label), cells))
    highlights = "".join("<li>{}</li>".format(html.escape(str(item))) for item in block.get("highlights", []))
    sources = " · ".join(html.escape(str(note.get("url"))) for note in data.get("source_notes", []))
    hero_css = "background-image:linear-gradient(90deg,rgba(5,8,16,.94),rgba(5,8,16,.68)),url('{}');".format(hero) if hero else "background-image:radial-gradient(circle at 85% 15%,#303b72,transparent 42%),linear-gradient(135deg,#080b16,#11182b);"
    css = """
*{box-sizing:border-box}body{margin:0;background:#080b14;color:#f5f7ff;font-family:Inter,Arial,sans-serif}.poster{width:1080px;min-height:1520px;padding:72px 68px 58px;position:relative;overflow:hidden;background-color:#080b14;HERO;background-size:cover;background-position:center top}.eyebrow{color:#70b7ff;letter-spacing:.18em;text-transform:uppercase;font-size:15px;font-weight:700}h1{font-size:66px;line-height:1.04;max-width:850px;margin:22px 0 18px;letter-spacing:-.045em}.lead{font-size:24px;line-height:1.45;max-width:820px;color:#d3d9eb;margin:0 0 42px}.table-wrap{background:rgba(8,11,20,.86);border:1px solid rgba(255,255,255,.17);border-radius:20px;overflow:hidden;box-shadow:0 22px 80px rgba(0,0,0,.35)}table{width:100%;border-collapse:collapse;font-size:19px}th,td{padding:21px 18px;border-bottom:1px solid rgba(255,255,255,.1);text-align:left;vertical-align:top}thead th{font-size:23px;color:#dce6ff}thead th small{display:block;font-size:12px;color:#ff7c89;letter-spacing:.1em;margin-top:6px}tr:last-child th,tr:last-child td{border-bottom:0}td.hot,th.hot{background:rgba(57,135,255,.2);color:#fff}tbody th{color:#9ca9c3;font-weight:600;width:170px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:28px}.panel{padding:28px;border:1px solid rgba(255,255,255,.12);border-radius:18px;background:rgba(8,11,20,.78)}.panel h2{font-size:16px;letter-spacing:.18em;text-transform:uppercase;color:#ff7180;margin:0 0 16px}li{font-size:21px;line-height:1.42;margin:11px 0;color:#e0e6f4}.social{font-size:18px;line-height:1.55;white-space:pre-wrap;color:#d3d9eb}footer{margin-top:38px;color:#93a1bc;font-size:13px;line-height:1.5;word-break:break-all}.mark{position:absolute;right:66px;top:70px;color:#ff7180;font-size:15px;letter-spacing:.2em;font-weight:700}@media(max-width:1080px){body{overflow-x:auto}}
""".replace("HERO", hero_css)
    title = html.escape(block["title"])
    lead = html.escape(block["lead"])
    metric = "指标" if language == "cn" else "Metric"
    return "<!doctype html><html lang='{}'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>{}</title><style>{}</style></head><body><main class='poster'><div class='mark'>MODEL UPDATE</div><div class='eyebrow'>{} · {}</div><h1>{}</h1><p class='lead'>{}</p><section class='table-wrap'><table><thead><tr><th>{}</th>{}</tr></thead><tbody>{}</tbody></table></section><div class='grid'><section class='panel'><h2>{}</h2><ul>{}</ul></section><section class='panel'><h2>{}</h2><div class='social'>{}</div></section></div><footer>Sources: {}</footer></main></body></html>".format(language, title, css, html.escape(data["topic"]), html.escape(data["as_of"]), title, lead, metric, headers, "".join(row_html), "Highlights" if language == "en" else "重点结论", highlights, "Social copy" if language == "en" else "社媒文案", html.escape(block.get("social", "")), sources)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("facts", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.facts.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    hero_value = data.get("hero_image") or config.get("hero_image")
    hero = ""
    if hero_value:
        path = Path(hero_value).expanduser()
        if not path.is_absolute() and config.get("asset_dir"):
            path = Path(config["asset_dir"]).expanduser() / path
        if not path.exists():
            raise SystemExit("hero image not found: {}".format(path))
        hero = image_data(path)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for lang, suffix in (("cn", ""), ("en", "-en")):
        (args.out_dir / "index{}.html".format(suffix)).write_text(page(data, lang, hero), encoding="utf-8")
    print("RENDERED: {}".format(args.out_dir))

if __name__ == "__main__":
    main()
