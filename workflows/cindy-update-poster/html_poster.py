#!/usr/bin/env python3
"""Build a self-contained Cindy editorial release poster for Chrome capture."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import secrets
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORDMARK = ROOT / "assets/brand/std-white.png"
POSE_DIR = ROOT / "assets/poses"
BACKGROUND_PACK = ROOT / "assets" / "backgrounds"
BACKGROUND_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
WORDMARK_SHA256 = "7ae927c07f7334e337e8f7c9217f8133a8d009032b2f653616528173e4cc9e4b"
WIDTH = 1240


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def data_uri(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def background_candidates() -> list[Path]:
    """Return source backgrounds only; index previews are never render inputs."""
    configured: list[Path] = []
    env_path = os.environ.get("CINDY_POSTER_BACKGROUND_DIR", "").strip()
    if env_path:
        configured.append(Path(env_path).expanduser())
    local_config = ROOT / "config.local.json"
    if local_config.exists():
        try:
            value = json.loads(local_config.read_text(encoding="utf-8")).get("background_dir")
            if value:
                path = Path(str(value)).expanduser()
                configured.append(path if path.is_absolute() else ROOT / path)
        except (OSError, ValueError, TypeError):
            pass
    configured.append(BACKGROUND_PACK)
    roots = []
    for root in configured:
        if root not in roots and root.exists():
            roots.append(root)
    candidates = []
    for pool in roots:
        for folder in ("01-used-backgrounds", "02-historical-variants"):
            root = pool / folder
            if root.exists():
                candidates.extend(
                    path for path in root.iterdir()
                    if path.is_file() and path.suffix.lower() in BACKGROUND_EXTENSIONS
                )
    return sorted(candidates)


def choose_background(cfg: dict) -> Path:
    """Choose an explicit background when supplied, otherwise sample the local pool."""
    visual = cfg.get("visual") or {}
    explicit = visual.get("background_path") or visual.get("background")
    if explicit:
        path = Path(str(explicit)).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise SystemExit(f"configured background asset missing: {path}")
        return path
    candidates = background_candidates()
    if candidates:
        return secrets.choice(candidates)
    raise SystemExit(
        "Cindy background pool is empty: "
        "set CINDY_POSTER_BACKGROUND_DIR or background_dir in config.local.json to a pool containing "
        "01-used-backgrounds/ and 02-historical-variants/"
    )


def has_cjk(value: str) -> bool:
    return any("㐀" <= char <= "鿿" for char in value)


def release_tags(value: object) -> list[str]:
    return re.findall(r"(?:^|[^0-9])v?(\d+\.\d+\.\d+)", str(value or ""))


def counts_for(cfg: dict, lang: str) -> tuple[tuple[str, str], ...]:
    counts = cfg.get("counts") or {}
    values = (
        (counts.get("features", 0), "项功能" if lang == "cn" else "FEATURES"),
        (counts.get("fixes", 0), "处修复" if lang == "cn" else "FIXES"),
        (counts.get("authors", counts.get("contributors", 0)), "位贡献者" if lang == "cn" else "CONTRIBUTORS"),
    )
    return tuple((str(number), label) for number, label in values)


def text_lines(cfg: dict, lang: str) -> tuple[str, str, str, list[dict], tuple[tuple[str, str], ...]]:
    block = cfg.get(lang) or {}
    weekly = cfg.get("period_type") == "weekly"
    limit = 12 if weekly else 8
    themes = [theme for theme in block.get("themes", []) if theme.get("title")][:limit]
    return (
        str(block.get("title") or ("本周更新" if weekly and lang == "cn" else "WEEKLY UPDATE" if weekly else "今日更新")),
        str(block.get("lead") or ""),
        str(cfg.get("date", "")),
        themes,
        counts_for(cfg, lang),
    )


GROUP_LABELS = {
    "feature": ("重点更新", "RELEASE HIGHLIGHTS", "NEW"),
    "fix": ("问题修复", "ISSUES FIXED", "FIXED"),
    "other": ("更多更新", "MORE", "MORE"),
}


def theme_card(theme: dict, index: int, cn: bool) -> str:
    kind = str(theme.get("kind") or "other")
    tag = "NEW" if kind == "feature" else "FIXED" if kind == "fix" else "MORE"
    publisher = str(theme.get("publisher") or theme.get("contributors") or "").strip()
    byline = f'<div class="byline">{esc(publisher)}</div>' if publisher else ""
    platform = {"D": "DESKTOP", "M": "MOBILE", "S": "SERVER"}.get(
        str(theme.get("platform") or "D").upper(),
        str(theme.get("platform") or "DESKTOP").upper(),
    )
    return f'''<article class="theme-card">
      <div class="theme-index">{index:02d}</div>
      <div class="theme-copy">
        <div class="theme-meta"><span>{tag}</span><span>{esc(platform)}</span></div>
        <h3>{esc(theme.get("title", ""))}</h3>
        <p>{esc(theme.get("description", ""))}</p>
        {byline}
      </div>
      <i class="corner-cut" aria-hidden="true"></i>
    </article>'''


def grouped_updates(themes: list[dict], cn: bool, weekly: bool) -> str:
    groups: list[tuple[str, list[dict]]] = []
    for kind in ("feature", "fix", "other"):
        items = [theme for theme in themes if str(theme.get("kind") or "other") == kind]
        if items:
            groups.append((kind, items))
    chunks: list[str] = []
    running = 1
    for kind, items in groups:
        label_cn, label_en, tag = GROUP_LABELS[kind]
        label = label_cn if cn else label_en
        cards = "".join(theme_card(theme, running + i, cn) for i, theme in enumerate(items))
        running += len(items)
        grid_class = " theme-grid-fixes" if kind == "fix" and len(items) > 1 else ""
        chunks.append(f'''<section class="update-group group-{kind}">
          <div class="group-bar"><span><b>{len(chunks)+1:02d}</b><strong>{esc(label)}</strong><em>/ {tag}</em></span><small>{len(items):02d}</small></div>
          <div class="theme-grid{grid_class}">{cards}</div>
        </section>''')
    return "".join(chunks)


def render(cfg: dict, lang: str, pose_name: str, background_path: Path) -> str:
    weekly = cfg.get("period_type") == "weekly"
    source_title, lead, date, themes, metrics = text_lines(cfg, lang)
    tags = release_tags(cfg.get("shipped"))
    latest = tags[-1] if tags else ""
    version_display = " / ".join(tags) if weekly else latest
    release_url = f"https://github.com/makecindy/cindy/releases/tag/v{latest}" if latest else ""
    wordmark = data_uri(WORDMARK)
    background = data_uri(background_path)
    cn = lang == "cn"
    headline = "本周更新" if weekly and cn else "WEEKLY UPDATE" if weekly else "今日更新" if cn else "TODAY'S UPDATE"
    release_name = source_title
    if release_name.lower().startswith("cindy "):
        release_name = release_name[6:].strip()
    if not release_name or release_name == version_display:
        release_name = "本周版本汇总" if weekly and cn else "WEEKLY RELEASE DOSSIER" if weekly else "RELEASE DOSSIER"
    chip_html = "".join(f'<span class="release-chip">v{esc(tag)}</span>' for tag in tags) if weekly else ""
    metric_html = "".join(f'<div class="metric"><strong>{esc(number)}</strong><span>{esc(label)}</span></div>' for number, label in metrics)
    updates_html = grouped_updates(themes, cn, weekly)
    all_credits = [str(name) for name in cfg.get("credits", []) if name]
    credits = list(all_credits)
    if not cn:
        credits = [name for name in credits if not has_cjk(name)]
    credit_html = "".join(f"<span>{esc(name)}</span>" for name in credits)
    counts = cfg.get("counts") or {}
    total_prs = str(counts.get("total_prs", ""))
    contributor_total = counts.get("authors", counts.get("contributors", len(all_credits)))
    period_word = "WEEK" if weekly else "RELEASE"
    badge = "WEEKLY" if weekly else ("日报" if cn else "UPDATE")
    footer_label = "本期贡献者" if cn else "CREDITS"
    update_count = len(themes)
    return f'''<!doctype html>
<html lang="{'zh-CN' if cn else 'en'}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width={WIDTH}, initial-scale=1">
<title>{esc(source_title)}</title>
<style>
@font-face{{font-family:Bebas;src:url("data:font/ttf;base64,{base64.b64encode((ROOT/'assets/brand/BebasNeue-Regular.ttf').read_bytes()).decode('ascii')}")}}
@font-face{{font-family:CN;src:local("Hiragino Sans GB"),local("PingFang SC"),local("STHeiti")}}
*{{box-sizing:border-box}} html,body{{margin:0;background:#02030a}}
html{{height:auto;overflow-x:hidden}} body{{width:{WIDTH}px;height:auto;min-height:0;overflow-x:hidden;overflow-y:visible;color:#f7f4f1;font-family:{'CN' if cn else 'Arial'},sans-serif}}
.poster{{position:relative;display:flex;flex-direction:column;width:{WIDTH}px;min-height:0;height:auto;overflow:visible;padding:78px 56px 48px;background:#05050d}}
.art{{position:absolute;z-index:1;inset:0;width:100%;height:100%;object-fit:cover;object-position:center top;filter:saturate(.96) contrast(1.08) brightness(.91)}}
.veil{{position:absolute;z-index:2;inset:0;background:rgba(2,3,10,.34);pointer-events:none}}
.veil:before{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(2,3,10,.94) 0%,rgba(2,3,10,.79) 31%,rgba(2,3,10,.34) 61%,rgba(2,3,10,.30) 100%),linear-gradient(0deg,rgba(2,3,10,.96) 0%,rgba(2,3,10,.10) 20%,rgba(2,3,10,.08) 75%,rgba(2,3,10,.72) 100%)}}
.veil:after{{content:"";position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent 0 7px,rgba(255,255,255,.025) 8px),linear-gradient(125deg,transparent 0 28%,rgba(247,1,33,.30) 28.1% 28.35%,transparent 28.45% 100%),radial-gradient(ellipse at 80% 50%,rgba(247,1,33,.18),transparent 34%)}}
.grain{{position:absolute;z-index:3;inset:0;opacity:.22;background:repeating-linear-gradient(90deg,transparent 0 23px,rgba(255,255,255,.018) 24px);mix-blend-mode:screen;pointer-events:none}}
.frame{{position:absolute;z-index:10;inset:18px;border:1px solid rgba(223,227,239,.50);pointer-events:none}}
.frame:before,.frame:after{{content:"";position:absolute;width:34px;height:34px;border-color:#f70121;border-style:solid}}
.frame:before{{left:-2px;top:-2px;border-width:4px 0 0 4px}} .frame:after{{right:-2px;bottom:-2px;border-width:0 4px 4px 0}}
.topline{{position:absolute;z-index:20;left:53px;right:53px;top:38px;height:42px;display:flex;align-items:center;gap:21px;color:#d9dce5}}
.topline img{{width:120px;height:auto}} .kicker{{color:#f70121;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:3px}}
.barcode{{width:155px;height:21px;margin-left:auto;background:repeating-linear-gradient(90deg,#e9ebf3 0 2px,transparent 2px 5px,#e9ebf3 5px 6px,transparent 6px 9px);opacity:.68}}
.topline .date{{color:#eef0f6;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.hero{{position:relative;z-index:15;width:674px}}
.hatch{{width:142px;height:11px;margin-bottom:16px;background:repeating-linear-gradient(110deg,#f70121 0 14px,transparent 14px 25px)}}
.eyebrow{{display:none;margin-bottom:12px;color:#f70121;font:17px/1 Bebas,Arial,sans-serif;letter-spacing:5px}}
h1{{margin:0 0 13px;color:#fff;font-family:{'CN' if cn else 'Bebas'},Arial,sans-serif;font-size:{'76px' if cn else '93px'};font-weight:700;line-height:.93;letter-spacing:{'2px' if cn else '2.3px'};text-transform:uppercase;text-shadow:0 4px 20px rgba(0,0,0,.84)}}
.release-name{{max-width:650px;margin-bottom:12px;color:#e0e2e9;font:{'20px' if cn else '21px'}/1.3 {'CN' if cn else 'Arial'},sans-serif;letter-spacing:{'0' if cn else '.2px'};text-shadow:0 2px 12px #000}}
.release-chips{{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 11px}} .release-chip{{padding:5px 9px 4px;border:1px solid rgba(247,1,33,.72);color:#f2f3f7;background:rgba(10,4,12,.48);font:13px/1 Bebas,Arial,sans-serif;letter-spacing:1.5px}}
.version-row{{display:flex;align-items:center;gap:14px;margin-bottom:13px}} .version{{color:#f70121;font:48px/1 Bebas,Arial,sans-serif;letter-spacing:2px;text-shadow:0 3px 14px rgba(0,0,0,.72)}}
.badge{{padding:7px 12px 6px;border:1px solid rgba(247,1,33,.92);color:#fff;background:#f70121;font:14px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.lead{{max-width:630px;color:#f4f3f5;font:21px/1.33 Arial,sans-serif;text-shadow:0 2px 14px rgba(0,0,0,.94)}}
.metrics{{display:flex;width:625px;margin-top:19px;border-top:1px solid rgba(247,1,33,.9);border-bottom:1px solid rgba(255,255,255,.28)}}
.metric{{width:33.333%;min-height:65px;padding:9px 12px 8px 0;border-right:1px solid rgba(255,255,255,.24)}} .metric:not(:first-child){{padding-left:16px}} .metric:last-child{{border-right:0}}
.metric strong{{display:block;color:#f70121;font:39px/1 Bebas,Arial,sans-serif;letter-spacing:1px}} .metric span{{display:block;margin-top:6px;color:#f6f3f5;font:{'14px' if cn else '13px'}/1.1 {'CN' if cn else 'Arial'},sans-serif;letter-spacing:{'0' if cn else '1px'};white-space:nowrap}}
.interval{{position:relative;top:auto;right:auto;margin-top:9px;color:#afb4c2;font:13px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.updates{{position:relative;z-index:16;width:790px;margin-top:18px;overflow:visible;padding:0;background:rgba(3,4,11,.22)}}
.update-group{{margin:0 0 13px}} .group-feature{{margin-bottom:52px}} .group-bar{{height:47px;display:flex;align-items:center;padding:0 14px;border-top:2px solid #f70121;border-bottom:1px solid rgba(255,255,255,.36);background:rgba(5,5,12,.93);color:#fff}}
.group-bar span{{display:flex;align-items:baseline;gap:11px}} .group-bar b{{color:#f70121;font:16px/1 Bebas,Arial,sans-serif;letter-spacing:1px}} .group-bar strong{{font:{'21px' if cn else '27px'}/1 {'CN' if cn else 'Bebas'},Arial,sans-serif;letter-spacing:{'1px' if cn else '1.5px'}}} .group-bar em{{color:#f70121;font:13px/1 Bebas,Arial,sans-serif;letter-spacing:2px;font-style:normal}} .group-bar small{{margin-left:auto;color:#f70121;font:14px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.theme-grid{{display:grid;grid-template-columns:1fr;gap:5px;margin-top:5px}} .theme-grid-fixes{{grid-template-columns:1fr 1fr;gap:7px}}
.theme-card{{position:relative;display:grid;grid-template-columns:43px 1fr;gap:4px;min-height:0;padding:13px 17px 12px 12px;border:1px solid rgba(173,179,196,.48);border-left:4px solid #f70121;background:linear-gradient(90deg,rgba(10,9,17,.91),rgba(10,9,17,.76));box-shadow:0 6px 18px rgba(0,0,0,.20)}}
.theme-index{{padding-top:2px;color:#f70121;font:16px/1 Bebas,Arial,sans-serif;letter-spacing:1px}} .theme-meta{{display:flex;gap:13px;margin-bottom:5px;color:#f70121;font:12px/1 Bebas,Arial,sans-serif;letter-spacing:1.6px}} .theme-meta span+span{{color:#abb0be}}
.theme-card h3{{margin:0 0 5px;color:#fff;font:{'22px' if cn else '21px'}/1.13 {'CN' if cn else 'Arial'},sans-serif;font-weight:700;letter-spacing:{'0' if cn else '.1px'};text-shadow:0 2px 9px #000}} .theme-card p{{margin:0;color:#d5d8e1;font:14px/1.30 {'CN' if cn else 'Arial'},sans-serif;text-shadow:0 2px 9px rgba(0,0,0,.96);overflow:visible}}
.byline{{margin-top:6px;color:#f70121;font:11px/1 Bebas,Arial,sans-serif;letter-spacing:1.3px}} .corner-cut{{position:absolute;right:-1px;bottom:-1px;width:15px;height:15px;background:rgba(5,5,12,.95);border-left:1px solid #f70121;border-top:1px solid #f70121;clip-path:polygon(100% 0,100% 100%,0 100%)}}
.bottom-meta{{position:relative;z-index:18;width:100%;margin-top:auto;padding:14px 15px 13px;border:1px solid rgba(173,179,196,.42);background:rgba(3,4,11,.79);color:#d9dce6}}
.meta-line{{display:flex;align-items:baseline;gap:14px;margin-bottom:10px;font:15px/1.25 {'CN' if cn else 'Arial'},sans-serif}} .meta-line b{{color:#f70121;font:15px/1 Bebas,Arial,sans-serif;letter-spacing:2px}} .meta-line span{{color:#eef0f5}}
.credits{{display:flex;flex-wrap:wrap;gap:7px 18px;color:#d6d9e2;font:14px/1.18 {'CN' if cn else 'Arial'},sans-serif}} .credits span{{white-space:nowrap}} .credits span+span:before{{content:"·";color:#f70121;margin-right:18px}}
.brand-lockup{{position:relative;z-index:18;width:350px;height:61px;margin:19px auto 0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;border:1px solid rgba(247,1,33,.36);background:rgba(3,4,11,.78)}}
.brand-lockup img{{width:72px;height:auto}} .brand-lockup span{{color:#f70121;font:11px/1 Bebas,Arial,sans-serif;letter-spacing:2px}}
.footer{{position:relative;z-index:18;width:100%;margin-top:10px;display:flex;justify-content:space-between;padding-top:10px;color:#adb3c1;font:11px/1.2 Bebas,Arial,sans-serif;letter-spacing:1.3px}} .footer .url{{max-width:730px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}}
.side-note{{position:absolute;z-index:18;right:37px;bottom:190px;color:rgba(255,255,255,.55);font:12px/1 Bebas,Arial,sans-serif;letter-spacing:3px;writing-mode:vertical-rl}}
@media (max-width:900px){{body{{transform-origin:top left}}}}
</style></head>
<body><main class="poster">
  <img class="art" src="{background}" alt="Cindy background artwork">
  <div class="veil"></div><div class="grain"></div><div class="frame"></div>
  <header class="topline"><img src="{wordmark}" alt="official Cindy wordmark"><span class="kicker">PATCH DOSSIER / CINDY</span><span class="barcode"></span><span class="date">{esc(date)}</span></header>
  <section class="hero"><div class="hatch"></div><div class="eyebrow">CONSIDER IT DONE</div><h1>{esc(headline)}</h1><div class="version-row"><span class="version">{esc(date)}</span><span class="badge">{badge}</span></div><div class="release-name">{esc(release_name)}</div><div class="release-chips">{chip_html}</div><div class="lead">{esc(lead)}</div><div class="metrics">{metric_html}</div><div class="interval">{esc(total_prs)} MERGED PRs / {period_word} INTERVAL</div></section>
  <section class="updates">{updates_html}</section>
  <section class="bottom-meta"><div class="meta-line"><b>{footer_label}</b><span>{esc(total_prs)} merged PRs · {esc(contributor_total)} contributors</span></div><div class="credits">{credit_html}</div></section>
  <div class="side-note">BUILD / SHIP / REPEAT</div>
  <footer class="footer"><span>v{esc(version_display)} · {esc(date)}</span><span class="url">{esc(release_url)}</span></footer>
  <div class="brand-lockup"><img src="{wordmark}" alt="Cindy"><span>CONSIDER IT DONE · {esc(date)}</span></div>
</main><script>(function(){{function measure(){{var p=document.querySelector('.poster');if(!p)return;var h=Math.ceil(p.getBoundingClientRect().height);document.documentElement.setAttribute("data-poster-height",String(h));var s=document.getElementById('poster-h');if(!s){{s=document.createElement('span');s.id='poster-h';s.style.display='none';document.body.appendChild(s);}}s.setAttribute('data-h',String(h));}}measure();if(document.fonts&&document.fonts.ready){{document.fonts.ready.then(function(){{measure();requestAnimationFrame(measure);}});}}window.addEventListener('load',function(){{measure();}});}})();</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "out" / "html")
    args = parser.parse_args()
    cfg = json.loads(args.source.read_text(encoding="utf-8"))
    if not WORDMARK.exists():
        raise SystemExit(f"official Cindy wordmark missing: {WORDMARK}")
    if hashlib.sha256(WORDMARK.read_bytes()).hexdigest() != WORDMARK_SHA256:
        raise SystemExit("official Cindy wordmark checksum mismatch")
    day = str(cfg["day_id"])
    pose_name = ((cfg.get("visual") or {}).get("reference_pose") or "pose-arms-crossed-with-cat")
    pose_path = POSE_DIR / f"{pose_name}.png"
    if not pose_path.exists():
        raise SystemExit(f"approved pose asset missing: {pose_path}")
    background_path = choose_background(cfg)
    print(f"background pool pick: {background_path}")
    for lang in ("cn", "en"):
        out = args.out_dir / f"{day}-{lang}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(cfg, lang, pose_name, background_path), encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()
