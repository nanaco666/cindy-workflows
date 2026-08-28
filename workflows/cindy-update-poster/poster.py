#!/usr/bin/env python3
"""CINDY daily update poster.

The default path generates editable HTML/CSS and captures it with local Chrome.
The historical Pillow layouts remain available only with ``--legacy-render``.
"""
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pose_library import apply as apply_pose_library, enabled_assets

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LAYOUTS = {
    "columns": "两栏对照 · 人物立于中间空档",
    "stack": "单列堆叠 · ①②③④ 编号区块 · 人物占右侧",
    "hero": "顶部横幅大图 · 标题压在人物上 · 正文通栏两列",
    "timeline": "竖脊时间线 · 版本与区块都是脊上的节点 · 人物立于脊末",
    "grid": "编辑式瀑布流 · 人物与主内容非对称编排",
    "portrait_editorial": "动态半身封面 · 主功能领衔 · 内容驱动编排",
    "portrait_backdrop": "人物全幅背景 · 磨砂黑透信息层 · 内容自适应",
}


def load(name):
    if name not in LAYOUTS:
        raise SystemExit(f"未知 layout: {name}（可用: {', '.join(LAYOUTS)}）")
    return importlib.import_module(f"layouts.{name}")


def pick(cfg, override=None):
    """Explicit flag > JSON field > rotate by date so consecutive days differ."""
    if override:
        return override
    if cfg.get("layout"):
        return cfg["layout"]
    order = list(LAYOUTS)
    return order[int(cfg["day_id"]) % len(order)]


def run_html(src, cfg, html_only):
    html_script = Path(HERE) / "html_poster.py"
    capture_script = Path(HERE) / "capture_poster.py"
    subprocess.run([sys.executable, str(html_script), str(src)], check=True)
    if html_only:
        return
    html_dir = Path(HERE) / "out" / "html"
    final_dir = Path(HERE) / "out" / "posters"
    for lang in ("cn", "en"):
        html_path = html_dir / f"{cfg['day_id']}-{lang}.html"
        out_path = final_dir / f"cindy-daily-{cfg['day_id']}-html-{lang}.png"
        subprocess.run([sys.executable, str(capture_script), str(html_path), str(out_path)], check=True)
        print(f"  {lang}: {out_path}")


def run_legacy(cfg, override):
    name = pick(cfg, override)
    mod = load(name)
    print(f"layout: {name} —— {LAYOUTS[name]}")
    selected_pose = apply_pose_library(cfg, name)
    if selected_pose:
        print(f"pose library: {selected_pose['name']} —— deterministic pick for {cfg['day_id']}")
    else:
        print(f"pose: {cfg.get('pose') or getattr(mod, 'POSE_DEFAULT', 'layout default')} —— explicit/default")

    import common
    if common.block_has_cjk(cfg["en"]):
        print("  ⚠ en 块仍含中文 —— 这是未编辑的草稿，英文版不可发布")
    if any("TODO" in t for t, _ in cfg["cn"]["summary"] + cfg["en"]["summary"]):
        print("  ⚠ summary 仍是 TODO 占位 —— 先写导语")
    for lang in ("cn", "en"):
        height = mod.render(cfg, lang, measure=True)
        mod.render(cfg, lang, bg_h=height)


def main():
    args = list(sys.argv[1:])
    if "--layouts" in args:
        for key, value in LAYOUTS.items():
            print(f"  {key:<20} {value}")
        return
    if "--poses" in args:
        print("  approved references  " + ", ".join(asset["name"] for asset in enabled_assets()))
        return

    legacy = "--legacy-render" in args
    html_only = "--html-only" in args
    for flag in ("--legacy-render", "--html-only"):
        if flag in args:
            args.remove(flag)
    override = None
    if "--layout" in args:
        index = args.index("--layout")
        override = args[index + 1]
        del args[index:index + 2]
    src = Path(args[0] if args else os.path.join(HERE, "content", "20260727.json"))
    cfg = json.loads(src.read_text(encoding="utf-8"))

    if not legacy:
        run_html(src, cfg, html_only)
        return
    run_legacy(cfg, override)


if __name__ == "__main__":
    main()
