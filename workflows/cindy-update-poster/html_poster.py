#!/usr/bin/env python3
"""Build a self-contained HTML/CSS Cindy release poster for browser capture."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORDMARK = ROOT / "assets/brand/std-white.png"
POSE_DIR = ROOT / "assets/poses"
WORDMARK_SHA256 = "7ae927c07f7334e337e8f7c9217f8133a8d009032b2f653616528173e4cc9e4b"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def has_cjk(value: str) -> bool:
    return any("㐀" <= char <= "鿿" for char in value)


def text_lines(cfg: dict, lang: str) -> tuple[str, str, str, list[dict], list[tuple[str, str]]]:
    block = cfg[lang]
    themes = [theme for theme in block.get("themes", []) if theme.get("title")]
    themes = themes[:6]
    if lang == "cn":
        metrics = [
            (str(cfg["counts"]["features"]), "项功能"),
            (str(cfg["counts"]["fixes"]), "处修复"),
            (str(cfg["counts"]["authors"]), "位贡献者"),
        ]
    else:
        metrics = [
            (str(cfg["counts"]["features"]), "FEATURES"),
            (str(cfg["counts"]["fixes"]), "FIXES"),
            (str(cfg["counts"]["authors"]), "CONTRIBUTORS"),
        ]
    return (
        str(block.get("title") or "今日更新"),
        str(block.get("lead") or ""),
        str(cfg.get("date", "")),
        themes,
        metrics,
    )


def render(cfg: dict, lang: str, pose_name: str) -> str:
    source_title, lead, date, themes, metrics = text_lines(cfg, lang)
    version = str(cfg.get("shipped", ""))
    release_url = f"https://github.com/makecindy/cindy/releases/tag/v{version}"
    wordmark = data_uri(WORDMARK)
    pose = data_uri(POSE_DIR / f"{pose_name}.png")
    cn = lang == "cn"
    headline = "更新公告" if cn else "TODAY'S UPDATE"
    release_name = source_title
    prefix = f"Cindy v{version}"
    if release_name.startswith(prefix):
        release_name = release_name[len(prefix):].strip("｜| :")
    if not release_name or release_name == version:
        release_name = "RELEASE DOSSIER"

    theme_html = "".join(
        f'''<article class="theme">
          <div class="theme-index">{i:02d}</div>
          <div class="theme-copy">
            <div class="theme-meta"><span>{"NEW" if theme.get("kind") == "feature" else "FIXED"}</span><span>{esc(theme.get("platform") or "D")}</span></div>
            <h2>{esc(theme.get("title", ""))}</h2>
            <p>{esc(theme.get("description", ""))}</p>
          </div>
          <i class="cut" aria-hidden="true"></i>
        </article>'''
        for i, theme in enumerate(themes, 1)
    )
    metric_html = "".join(
        f'<div class="metric"><strong>{esc(num)}</strong><span>{esc(label)}</span></div>'
        for num, label in metrics
    )
    credits = [str(name) for name in cfg.get("credits", []) if name]
    if not cn:
        credits = [name for name in credits if not has_cjk(name)]
    credit_html = "".join(f'<span>{esc(name)}</span>' for name in credits)
    total_prs = str((cfg.get("counts") or {}).get("total_prs", ""))
    theme_label = "更新重点" if cn else "RELEASE HIGHLIGHTS"
    footer_label = "本期贡献者" if cn else "CREDITS"
    return f'''<!doctype html>
<html lang="{'zh-CN' if cn else 'en'}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=1240, initial-scale=1">
<title>{esc(source_title)}</title>
<style>
@font-face{{font-family:Bebas;src:url("data:font/ttf;base64,{base64.b64encode((ROOT/'assets/brand/BebasNeue-Regular.ttf').read_bytes()).decode('ascii')}")}}
@font-face{{font-family:CN;src:local("Hiragino Sans GB"),local("PingFang SC"),local("STHeiti")}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:#03040b}}
body{{width:1240px;height:1754px;overflow:hidden;color:#f7f4f1;font-family:{'CN' if cn else 'Arial'},sans-serif}}
.poster{{position:relative;width:1240px;height:1754px;overflow:hidden;background:#060711}}
/* A real art plate sits underneath the whole composition. The copy never owns the canvas. */
.art{{position:absolute;z-index:1;inset:0;width:100%;height:100%;object-fit:cover;object-position:center center;filter:saturate(.88) contrast(1.08) brightness(.86)}}
.veil{{position:absolute;z-index:2;inset:0;background:rgba(2,3,10,.46);pointer-events:none}}
.veil:before{{content:"";position:absolute;inset:0;background:
  linear-gradient(90deg,rgba(2,3,10,.88) 0%,rgba(2,3,10,.70) 32%,rgba(2,3,10,.22) 69%,rgba(2,3,10,.40) 100%),
  linear-gradient(0deg,rgba(2,3,10,.93) 0%,rgba(2,3,10,.05) 20%,rgba(2,3,10,.10) 74%,rgba(2,3,10,.62) 100%)}}
.veil:after{{content:"";position:absolute;inset:0;background:
  linear-gradient(128deg,transparent 0 31%,rgba(247,1,33,.48) 31.1% 31.45%,transparent 31.55% 100%),
  linear-gradient(128deg,transparent 0 63%,rgba(247,1,33,.24) 63.1% 63.35%,transparent 63.45% 100%),
  radial-gradient(ellipse at 78% 57%,rgba(247,1,33,.22),transparent 33%)}}
.grain{{position:absolute;z-index:3;inset:0;opacity:.26;background:repeating-linear-gradient(0deg,transparent 0 7px,rgba(255,255,255,.035) 8px),repeating-linear-gradient(90deg,transparent 0 19px,rgba(255,255,255,.018) 20px);mix-blend-mode:screen;pointer-events:none}}
.frame{{position:absolute;z-index:10;inset:20px;border:1px solid rgba(234,238,250,.46);pointer-events:none}}
.frame:before,.frame:after{{content:"";position:absolute;width:42px;height:42px;border-color:#f70121;border-style:solid}}
.frame:before{{left:-2px;top:-2px;border-width:4px 0 0 4px}}
.frame:after{{right:-2px;bottom:-2px;border-width:0 4px 4px 0}}
.topline{{position:absolute;z-index:12;left:52px;right:52px;top:38px;height:40px;display:flex;align-items:center;gap:22px;color:#d5d8e5;font:15px/1 Arial,sans-serif;letter-spacing:2.7px}}
.topline img{{width:123px;height:auto}}
.topline .kicker{{color:#f70121;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:3px}}
.barcode{{width:142px;height:22px;margin-left:auto;background:repeating-linear-gradient(90deg,#f0f2fb 0 2px,transparent 2px 5px,#f0f2fb 5px 6px,transparent 6px 9px);opacity:.72}}
.topline .date{{color:#e7eaf2;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.hero{{position:absolute;z-index:11;left:70px;top:143px;width:635px}}
.hatch{{width:154px;height:12px;margin-bottom:27px;background:repeating-linear-gradient(110deg,#f70121 0 15px,transparent 15px 27px)}}
.eyebrow{{margin-bottom:13px;color:#f70121;font:17px/1 Bebas,Arial,sans-serif;letter-spacing:5px}}
h1{{margin:0 0 13px;color:#fff;font-family:{'CN' if cn else 'Bebas'},Arial,sans-serif;font-size:{'78px' if cn else '96px'};font-weight:700;line-height:.94;letter-spacing:{'2px' if cn else '2.5px'};text-transform:uppercase;text-shadow:0 4px 20px rgba(0,0,0,.76)}}
.release-name{{max-width:610px;margin-bottom:18px;color:#d9dce8;font:{'20px' if cn else '21px'}/1.3 {'CN' if cn else 'Arial'},sans-serif;letter-spacing:{'0' if cn else '.3px'};text-shadow:0 2px 12px #000}}
.version-row{{display:flex;align-items:center;gap:15px;margin-bottom:18px}}
.version{{color:#f70121;font:58px/1 Bebas,Arial,sans-serif;letter-spacing:2px;text-shadow:0 3px 14px rgba(0,0,0,.66)}}
.badge{{padding:7px 13px 6px;border:1px solid rgba(247,1,33,.9);color:#fff;background:#f70121;font:14px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.lead{{max-width:570px;color:#f1f2f5;font:23px/1.38 Arial,sans-serif;text-shadow:0 2px 14px rgba(0,0,0,.9)}}
.lead.cn{{font-family:CN,Arial,sans-serif;font-size:25px;line-height:1.42}}
.metrics{{display:flex;width:610px;margin-top:30px;border-top:1px solid rgba(247,1,33,.82);border-bottom:1px solid rgba(255,255,255,.22)}}
.metric{{width:33.333%;min-height:71px;padding:11px 12px 9px 0;border-right:1px solid rgba(255,255,255,.22)}}
.metric:not(:first-child){{padding-left:16px}}
.metric:last-child{{border-right:0}}
.metric strong{{display:block;color:#f70121;font:43px/1 Bebas,Arial,sans-serif;letter-spacing:1px}}
.metric span{{display:block;margin-top:7px;color:#f5f2f5;font:{'15px' if cn else '14px'}/1.1 {'CN' if cn else 'Arial'},sans-serif;letter-spacing:{'0' if cn else '1.1px'};white-space:nowrap}}
.interval{{position:absolute;top:28px;right:0;color:#acb1c0;font:13px/1 Bebas,Arial,sans-serif;letter-spacing:2.1px}}
.updates{{position:absolute;z-index:12;left:70px;top:692px;width:700px;padding:0 0 5px;background:rgba(2,3,10,.57);box-shadow:0 13px 40px rgba(0,0,0,.22)}}
.section-head{{display:flex;align-items:baseline;padding:13px 16px 12px;border-top:2px solid #f70121;border-bottom:1px solid rgba(255,255,255,.34);color:#fff;font:{'23px' if cn else '30px'}/1 {'CN' if cn else 'Bebas'},Arial,sans-serif;letter-spacing:{'1px' if cn else '1.6px'}}}
.section-head small{{margin-left:auto;color:#f70121;font:14px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.theme{{position:relative;display:grid;grid-template-columns:56px 1fr;gap:5px;min-height:166px;padding:18px 22px 18px 16px;border-bottom:1px solid rgba(255,255,255,.25)}}
.theme-index{{padding-top:3px;color:#f70121;font:17px/1 Bebas,Arial,sans-serif;letter-spacing:1px}}
.theme-meta{{display:flex;gap:12px;margin-bottom:7px;color:#f70121;font:13px/1 Bebas,Arial,sans-serif;letter-spacing:1.8px}}
.theme-meta span+span{{color:#a8adba}}
.theme h2{{margin:0 0 8px;color:#fff;font:{'25px' if cn else '26px'}/1.1 {'CN' if cn else 'Arial'},sans-serif;font-weight:700;letter-spacing:{'0' if cn else '.1px'};text-shadow:0 2px 9px #000}}
.theme p{{max-width:590px;margin:0;color:#d7dae4;font:16px/1.42 {'CN' if cn else 'Arial'},sans-serif;text-shadow:0 2px 9px rgba(0,0,0,.95)}}
.cut{{position:absolute;right:0;bottom:-1px;width:17px;height:17px;border-left:1px solid #f70121;border-top:1px solid #f70121;clip-path:polygon(100% 0,100% 100%,0 100%);background:rgba(2,3,10,.82)}}
.bottom-meta{{position:absolute;z-index:12;left:70px;right:70px;top:1373px;padding-top:14px;border-top:1px solid rgba(247,1,33,.75);color:#d9dce6}}
.meta-line{{display:flex;align-items:baseline;gap:14px;margin-bottom:13px;font:15px/1.25 {'CN' if cn else 'Arial'},sans-serif}}
.meta-line b{{color:#f70121;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.meta-line span{{color:#f0f1f6}}
.credits{{display:flex;flex-wrap:wrap;gap:8px 20px;max-width:1000px;color:#d2d5df;font:14px/1.1 {'CN' if cn else 'Arial'},sans-serif}}
.credits:before{{content:"";display:block;width:100%;height:1px;margin-bottom:2px;background:rgba(255,255,255,.18)}}
.credits span{{white-space:nowrap}}
.footer{{position:absolute;z-index:12;left:70px;right:70px;bottom:44px;display:flex;justify-content:space-between;gap:22px;padding-top:14px;border-top:1px solid rgba(247,1,33,.78);color:#c8ccd8;font:14px/1.2 Bebas,Arial,sans-serif;letter-spacing:1.5px;text-shadow:0 2px 8px #000}}
.footer .url{{max-width:730px;color:#9fa6b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}}
.side-note{{position:absolute;z-index:12;right:53px;bottom:128px;color:rgba(255,255,255,.58);font:13px/1 Bebas,Arial,sans-serif;letter-spacing:3px;writing-mode:vertical-rl}}
</style></head>
<body><main class="poster">
  <img class="art" src="{pose}" alt="approved Cindy character artwork">
  <div class="veil"></div><div class="grain"></div><div class="frame"></div>
  <header class="topline"><img src="{wordmark}" alt="official Cindy wordmark"><span class="kicker">CINDY PATCH DOSSIER</span><span class="barcode"></span><span class="date">{esc(date)}</span></header>
  <section class="hero"><div class="hatch"></div><div class="eyebrow">CONSIDER IT DONE</div><h1>{esc(headline)}</h1><div class="release-name">{esc(release_name)}</div><div class="version-row"><span class="version">PATCH {esc(version)}</span><span class="badge">UPDATE</span></div><div class="lead">{esc(lead)}</div><div class="metrics">{metric_html}</div><div class="interval">{esc(total_prs)} MERGED PRs / RELEASE INTERVAL</div></section>
  <section class="updates"><div class="section-head"><span>01&nbsp;&nbsp;{theme_label}</span><small>{len(themes):02d} THEMES</small></div>{theme_html}</section>
  <section class="bottom-meta"><div class="meta-line"><b>{footer_label}</b><span>{esc(total_prs)} merged PRs · {len(cfg.get('credits', []))} contributors</span></div><div class="credits">{credit_html}</div></section>
  <div class="side-note">BUILD / SHIP / REPEAT</div>
  <footer class="footer"><span>v{esc(version)} · {esc(date)}</span><span class="url">{esc(release_url)}</span></footer>
</main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "out" / "html")
    args = parser.parse_args()
    cfg = json.loads(args.source.read_text(encoding="utf-8"))
    if not WORDMARK.exists():
        raise SystemExit(f"official Cindy wordmark missing: {WORDMARK}")
    actual = hashlib.sha256(WORDMARK.read_bytes()).hexdigest()
    if actual != WORDMARK_SHA256:
        raise SystemExit("official Cindy wordmark checksum mismatch")
    day = str(cfg["day_id"])
    pose = ((cfg.get("visual") or {}).get("reference_pose") or "pose-arms-crossed-with-cat")
    pose_path = POSE_DIR / f"{pose}.png"
    if not pose_path.exists():
        raise SystemExit(f"approved pose asset missing: {pose_path}")
    for lang in ("cn", "en"):
        out = args.out_dir / f"{day}-{lang}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(cfg, lang, pose), encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()
