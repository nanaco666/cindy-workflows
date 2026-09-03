#!/usr/bin/env python3
"""Collect one day's public releases and the full merged-PR release delta.

    python3 collect.py 2026-07-27          # -> content/20260727.raw.json

Release notes and merged PRs answer different questions. The notes are curated,
user-facing themes and prove that a build shipped. The compare range from the
previous public release commit to each new release commit is the complete source
for feature/fix counts and contributors. Never use the number of note topics as
the release total.

Several releases a day is normal — every release published on the target date
(GMT+8) is collected, not just the newest. Version numbers also skip in the
public list when a build only went to the canary channel; day-grouping absorbs
that.

This script fetches both layers: selected release-note topics for editorial copy,
and every merged PR included in the released commit range for full statistics.
It also records calendar-day merges separately so a daily engineering summary
cannot be confused with a version announcement.
"""
import json, os, re, subprocess, sys
from collections import Counter
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
NAME_CACHE = os.path.join(HERE, ".authors.json")
CLIENT_REPO = "makecindy/cindy"
SERVER_REPO = "xindong/cindy-server"
CST = timezone(timedelta(hours=8))

def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"gh {' '.join(args[:3])}… failed:\n{r.stderr.strip()}")
    return r.stdout

def local(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(CST)

# ---------------------------------------------------------------- authors
def load_names():
    return json.load(open(NAME_CACHE)) if os.path.exists(NAME_CACHE) else {}

def display_name(login, cache):
    if login not in cache:
        try:
            n = gh("api", f"users/{login}", "--jq", ".name").strip()
        except SystemExit:
            n = ""
        cache[login] = n if n and n != "null" else login
    return cache[login]

# ---------------------------------------------------------------- parsing
SECTIONS = {"new features": "features", "bug fixes": "fixes"}
META = re.compile(r"^-\s+(commit|source tag|regions)\b")
TOPIC_FIX_HINTS = re.compile(r"输入|计费|稳定|诊断|自愈|过载|修复|故障|崩溃|卡死")
RELEASE_COMMIT = re.compile(r"^-\s+commit:\s*`([0-9a-f]{7,40})`", re.I | re.M)
PR_TYPE = re.compile(r"^([A-Za-z]+)(?:\([^)]*\))?:")
PR_NUMBER_PATTERNS = (
    re.compile(r"\(#(\d+)\)$"),
    re.compile(r"^Merge pull request #(\d+)\b", re.I),
)

def authored_text(text, cache):
    """Strip @mentions from copy while preserving every publisher in order."""
    logins = re.findall(r"@([A-Za-z0-9][A-Za-z0-9_-]*)", text)
    names = []
    for login in logins:
        # Product copy may describe Jira/IM "@mention" support. That token is
        # prose, not a GitHub publisher, and must remain visible in the note.
        if login.lower() in {"mention", "mentions"}:
            continue
        name = display_name(login, cache)
        if name not in names:
            names.append(name)
    clean = re.sub(
        r"\s*@(?!mentions?\b)[A-Za-z0-9][A-Za-z0-9_-]*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ，,。.")
    return clean, " · ".join(names)

def parse_notes(body, cache):
    """Release notes -> {features: [...], fixes: [...]}, each item
    {text, author, platform_hint}."""
    out = {"features": [], "fixes": []}
    section = None
    for line in body.splitlines():
        h = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if h:
            section = SECTIONS.get(h.group(1).strip().lower())
            continue
        if not section or not line.startswith("- ") or META.match(line):
            continue
        text, authors = authored_text(line[2:].strip(), cache)
        # the team prefixes mobile-only entries; everything else is desktop
        hint = "M" if re.match(r"^(Mobile|移动端|手机端)\s*[:：]", text) else "D"
        text = re.sub(r"^(Mobile|移动端|手机端)\s*[:：]\s*", "", text)
        out[section].append({
            "text": text,
            "author": authors,
            "platform_hint": hint,
        })

    # Newer releases use one H3 topic plus a paragraph instead of the historical
    # New Features / Bug Fixes bullet lists. Parse those topics only when the old
    # structure produced nothing, so both formats remain valid.
    if out["features"] or out["fixes"]:
        return out

    topics = []
    title, lines = None, []

    def flush_topic():
        nonlocal title, lines
        if not title:
            return
        paragraph = " ".join(s.strip() for s in lines if s.strip() and not s.startswith("- "))
        if paragraph:
            text, authors = authored_text(paragraph, cache)
            clean_title = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", title).strip()
            hint = "A" if re.search(r"移动端|手机端|iOS|Android", text, re.I) else "D"
            bucket = "fixes" if TOPIC_FIX_HINTS.search(clean_title) else "features"
            topics.append((bucket, {
                "text": f"{clean_title}——{text}",
                "author": authors,
                "platform_hint": hint,
            }))
        title, lines = None, []

    for line in body.splitlines():
        if line.strip() == "---":
            flush_topic()
            break
        h = re.match(r"^###\s+(.+?)\s*$", line)
        if h:
            flush_topic()
            candidate = h.group(1).strip()
            title = None if candidate.lower() in SECTIONS else candidate
            continue
        if title:
            lines.append(line)
    else:
        flush_topic()

    for bucket, item in topics:
        out[bucket].append(item)
    return out

def release_commit(body):
    """Return the exact shipped commit embedded in the release footer."""
    match = RELEASE_COMMIT.search(body)
    return match.group(1) if match else ""

def title_type(title):
    match = PR_TYPE.match(title)
    return match.group(1).lower() if match else "other"

def compare_pr_numbers(base, head):
    """Extract merged PR numbers from every commit in a release compare range.

    GitHub's compare endpoint paginates commits. Direct commits are kept in the
    audit output but deliberately excluded from PR counts.
    """
    commits, page, total = [], 1, None
    while total is None or len(commits) < total:
        data = json.loads(gh(
            "api",
            f"repos/{CLIENT_REPO}/compare/{base}...{head}?per_page=100&page={page}",
        ))
        batch = data.get("commits", [])
        if total is None:
            total = data.get("total_commits", len(batch))
        if not batch:
            break
        commits.extend(batch)
        page += 1

    numbers, unmatched, seen = [], [], set()
    for commit in commits:
        subject = commit["commit"]["message"].splitlines()[0]
        number = None
        for pattern in PR_NUMBER_PATTERNS:
            if match := pattern.search(subject):
                number = int(match.group(1))
                break
        if number is None:
            unmatched.append({"sha": commit["sha"], "subject": subject})
        elif number not in seen:
            seen.add(number)
            numbers.append(number)
    return numbers, unmatched, total or 0

def merged_pr_catalog():
    """Recent merged PR metadata, sufficient for daily release intervals."""
    rows = json.loads(gh(
        "pr", "list", "-R", CLIENT_REPO,
        "--state", "merged", "--limit", "1000",
        "--json", "number,title,author,mergedAt,url",
    ))
    return {row["number"]: row for row in rows}

def pr_record(pr, cache, release=""):
    login = (pr.get("author") or {}).get("login") or "ghost"
    return {
        "number": pr["number"],
        "title": pr["title"],
        "type": title_type(pr["title"]),
        "author_login": login,
        "author": display_name(login, cache) if login != "ghost" else "ghost",
        "merged_at": pr.get("mergedAt") or "",
        "url": pr.get("url") or "",
        "release": release,
    }

def pr_counts(prs):
    kinds = Counter(pr["type"] for pr in prs)
    authors = {pr["author_login"] for pr in prs}
    return {
        "total_prs": len(prs),
        "features": kinds["feat"],
        "fixes": kinds["fix"],
        "authors": len(authors),
        "other": len(prs) - kinds["feat"] - kinds["fix"],
        "types": dict(sorted(kinds.items())),
    }

# ---------------------------------------------------------------- collect
def collect(date_str):
    y, m, d = (int(x) for x in date_str.split("-"))
    cache = load_names()

    rels = json.loads(gh("release", "list", "-R", CLIENT_REPO, "--limit", "100",
                         "--json", "tagName,publishedAt,isPrerelease,isDraft"))
    # Only formal public releases define the shipped interval. Canary/beta
    # releases are internal and must never become the previous public release
    # or a version-total shortcut.
    rels = [r for r in rels if not r.get("isPrerelease") and not r.get("isDraft")]
    rels.sort(key=lambda r: r["publishedAt"])
    todays = [r for r in rels if (t := local(r["publishedAt"])).date().isoformat() == date_str]
    if not todays:
        print(f"{date_str}: 该日没有公开 release；仍会记录当天 merged PR，不能写版本已发布。")

    releases, features, fixes, bodies = [], [], [], {}
    for r in todays:
        body = gh("release", "view", r["tagName"], "-R", CLIENT_REPO, "--json", "body", "--jq", ".body")
        bodies[r["tagName"]] = body
        p = parse_notes(body, cache)
        for it in p["features"] + p["fixes"]:
            it["release"] = r["tagName"]
        releases.append({"tag": r["tagName"], "published": local(r["publishedAt"]).strftime("%H:%M"),
                         "features": len(p["features"]), "fixes": len(p["fixes"])})
        features += p["features"]
        fixes += p["fixes"]

    def dedupe(items):
        seen, out = set(), []
        for it in items:
            k = re.sub(r"\W+", "", it["text"])[:40]
            if k and k not in seen:
                seen.add(k); out.append(it)
        return out

    features, fixes = dedupe(features), dedupe(fixes)

    # Full release totals come from merged PRs in the exact shipped commit
    # range. Release-note topics above remain the curated editorial layer.
    catalog = merged_pr_catalog()
    day_prs = []
    for pr in catalog.values():
        if pr.get("mergedAt") and local(pr["mergedAt"]).date().isoformat() == date_str:
            day_prs.append(pr_record(pr, cache))
    day_prs.sort(key=lambda pr: pr["merged_at"])

    release_prs, intervals, seen_prs = [], [], set()
    if todays:
        first_at = todays[0]["publishedAt"]
        previous = next((r for r in reversed(rels) if r["publishedAt"] < first_at), None)
        previous_tag = previous["tagName"] if previous else ""
        previous_body = (gh("release", "view", previous_tag, "-R", CLIENT_REPO,
                            "--json", "body", "--jq", ".body") if previous else "")
        previous_commit = release_commit(previous_body)

        for release in todays:
            tag = release["tagName"]
            current_commit = release_commit(bodies[tag])
            interval = {
                "base_tag": previous_tag,
                "base_commit": previous_commit,
                "head_tag": tag,
                "head_commit": current_commit,
                "pull_requests": 0,
                "direct_commits": [],
                "unresolved_pr_numbers": [],
            }
            if previous_commit and current_commit:
                numbers, direct_commits, total_commits = compare_pr_numbers(
                    previous_commit, current_commit
                )
                interval["total_commits"] = total_commits
                interval["direct_commits"] = direct_commits
                for number in numbers:
                    pr = catalog.get(number)
                    if pr is None:
                        # Commit subjects occasionally contain an Issue number
                        # in the same ``(#1234)`` shape as a squash-merge PR.
                        # Only a real merged-PR record is allowed into totals;
                        # unresolved numbers stay visible for audit instead of
                        # aborting the whole day's collection.
                        interval["unresolved_pr_numbers"].append(number)
                        continue
                    if number not in seen_prs:
                        release_prs.append(pr_record(pr, cache, tag))
                        seen_prs.add(number)
                interval["pull_requests"] = len(
                    [n for n in numbers if n in catalog]
                )
            intervals.append(interval)
            previous_tag, previous_commit = tag, current_commit

    counted_prs = release_prs if release_prs else day_prs
    counts_scope = "release_interval" if release_prs else "calendar_day"
    counts = pr_counts(counted_prs)
    authors = []
    for pr in counted_prs:
        if pr["author"] not in authors:
            authors.append(pr["author"])

    release_note_authors = []
    for it in features + fixes:
        for name in it["author"].split(" · ") if it["author"] else []:
            if name not in release_note_authors:
                release_note_authors.append(name)

    # server side ships by merging main -> release, which auto-deploys to prod
    server = []
    lo = datetime(y, m, d, tzinfo=CST).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (datetime(y, m, d, tzinfo=CST) + timedelta(days=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        prs = json.loads(gh("pr", "list", "-R", SERVER_REPO, "--state", "merged", "--limit", "100",
                            "--search", f"merged:>={lo} merged:<{hi}", "--json", "number,title,mergedAt"))
        server = [{"number": p["number"], "title": p["title"],
                   "at": local(p["mergedAt"]).strftime("%H:%M")}
                  for p in prs if p["title"].startswith("release(")]
    except SystemExit:
        pass

    day_id = f"{y:04d}{m:02d}{d:02d}"
    raw = {
        "date": f"{y:04d}.{m:02d}.{d:02d}",
        "day_id": day_id,
        "shipped": " / ".join(r["tag"].lstrip("v") for r in releases),
        "releases": releases,
        "counts_scope": counts_scope,
        "counts": counts,
        "release_note_counts": {
            "features": len(features),
            "fixes": len(fixes),
            "authors": len(release_note_authors),
        },
        "release_intervals": intervals,
        "pull_requests": release_prs,
        "day_counts": pr_counts(day_prs),
        "day_merged_prs": day_prs,
        "features": features,
        "fixes": fixes,
        "authors": authors,
        "release_note_authors": release_note_authors,
        "server_deploys": server,
    }
    json.dump(cache, open(NAME_CACHE, "w"), ensure_ascii=False, indent=1)
    os.makedirs(CONTENT, exist_ok=True)
    path = os.path.join(CONTENT, f"{day_id}.raw.json")
    json.dump(raw, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"{raw['date']}  版本 {raw['shipped'] or '(无)'}")
    for r in releases:
        print(f"  {r['tag']:<9} {r['published']}  精选主题 {r['features'] + r['fixes']:>2}")
    print(f"  版本完整 PR: {counts['total_prs']} 个 —— feat {counts['features']}  "
          f"fix {counts['fixes']}  其他 {counts['other']}  贡献者 {counts['authors']}")
    print(f"  当天 merged PR: {raw['day_counts']['total_prs']} 个 —— "
          f"feat {raw['day_counts']['features']}  fix {raw['day_counts']['fixes']}  "
          f"贡献者 {raw['day_counts']['authors']}")
    if server:
        print(f"  服务端生产发布 {len(server)} 次: " + ", ".join(f"#{s['number']}@{s['at']}" for s in server))
    mob = [it for it in features + fixes if it["platform_hint"] == "M"]
    if mob:
        print(f"  ⚠ {len(mob)} 条标注为移动端 —— 客户端 release 只产出 dmg/exe，"
              f"移动端是否出包需另行确认")
    print(f"→ {path}")
    build_draft(raw)
    return raw

# ---------------------------------------------------------------- draft
def split_title(text):
    """Release bullets lead with the headline and separate detail with ——.
    Good enough for a draft; the punchy title is still an editorial rewrite."""
    for sep in ("——", "—", "："):
        if sep in text:
            head, _, rest = text.partition(sep)
            if 4 <= len(head) <= 22:
                return head.strip("，,。 "), rest.strip("，,。 ") or head
    head, _, rest = text.partition("，")
    if 4 <= len(head) <= 22 and rest:
        return head.strip(), rest.strip()
    return text[:16], text

def build_draft(raw):
    """Create an editorial draft without deciding the final visual structure.

    The complete Release-note topic list is retained under
    ``editorial.source_themes``. New language blocks contain visible editorial
    copy only and deliberately carry no card/layout vocabulary.
    """
    day_id = raw["day_id"]
    path = os.path.join(CONTENT, f"{day_id}.json")
    if os.path.exists(path):
        print(f"  (已存在，未覆盖: {os.path.basename(path)})")
        return path

    def theme(it, kind):
        title, desc = split_title(it["text"])
        return {"kind": kind, "title": title, "description": desc,
                "publisher": it.get("author", ""), "platform": it.get("platform_hint", "A"),
                "release": it.get("release", "")}

    source_themes = ([theme(i, "feature") for i in raw["features"]] +
                     [theme(i, "fix") for i in raw["fixes"]])

    def block(title):
        return {
            "title": title,
            "lead": "TODO 写一句面向用户的导语",
            # Start complete. The editor may merge related themes or shorten
            # descriptions without changing the factual source/audit layer.
            "themes": [dict(item) for item in source_themes],
            "community": {"title": "", "lines": []},
        }

    cfg = {
        "date": raw["date"], "day_id": day_id, "shipped": raw["shipped"],
        # Full totals from merged PRs in the shipped commit range. The poster
        # still shows a concise editorial grouping of those PRs.
        "counts": raw["counts"],
        "counts_scope": raw.get("counts_scope", ""),
        "release_note_counts": raw.get("release_note_counts", {}),
        "release_intervals": raw.get("release_intervals", []),
        "pull_requests": raw.get("pull_requests", []),
        "day_counts": raw.get("day_counts", {}),
        "day_merged_prs": raw.get("day_merged_prs", []),
        "server_deploys": raw.get("server_deploys", []),
        "cn": block("今日更新"),
        "en": block("WHAT'S NEW"),
        "credits": raw["authors"],
        "editorial": {
            "focus": "",
            "source_themes": source_themes,
            "instruction": "Rewrite for user impact; do not invent missing sections or filler content.",
        },
        "visual": {
            "direction": "",
            "aspect_ratio": "4:5 portrait",
            "mood": "",
            "safe_zones": {},
        },
    }
    json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"→ {path}")
    print(f"  草稿: 已保留完整精选主题 —— 新功能 {len(raw['features'])} 条 / 修复 {len(raw['fixes'])} 条")
    print("  ⚠ 待编辑: editorial.focus、cn/en 的 lead/themes/community；英文块当前仍需完整翻译")
    return path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python3 collect.py YYYY-MM-DD")
    collect(sys.argv[1])
