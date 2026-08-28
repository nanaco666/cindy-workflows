#!/usr/bin/env python3
"""Flag common canned-language, promise, and boundary problems in support drafts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from chinese_script import normalize_simplified, script_mismatch_error


PHRASE_WARNINGS = {
    r"感谢(?:您|你)宝贵的反馈": "generic acknowledgment; reflect a specific idea instead",
    r"(?:您|你)的反馈对我们(?:非常)?重要": "generic claim; state the concrete action or judgment",
    r"给(?:您|你)带来(?:的)?不便.{0,8}(?:深表歉意|敬请谅解)": "canned apology; name the actual disruption",
    r"有任何问题.{0,12}(?:随时|欢迎).{0,8}(?:联系|告诉)": "automatic open ending may create another round",
    r"请(?:您|你)耐心等待": "waiting request needs an owner or concrete next update",
    r"We value your feedback": "generic acknowledgment; reflect a specific idea instead",
    r"Your feedback is (?:very )?important to us": "generic claim; state the concrete action or judgment",
    r"Rest assured": "canned reassurance; state the verified fact directly",
    r"Please (?:do not hesitate|don't hesitate)": "formal open-ended filler",
    r"If you have any (?:other )?questions": "automatic open ending may create another round",
    r"Feel free to": "automatic invitation may be unnecessary",
    r"Thanks for explaining both needs\.?": "abstract closing; name what the sender wanted or use a simpler natural thanks",
    r"shared with the (?:relevant |appropriate )?team": "verify that the handoff actually occurred",
    r"forwarded to the (?:relevant |appropriate )?team": "verify that the handoff actually occurred",
    r"已(?:反馈|同步|转交|提交)(?:提醒)?给(?:相关|对应|负责)?(?:产品|技术|账号|客服)?(?:团队|同事|专人)": "verify that the handoff actually occurred",
    r"(?:我们)?(?:会|将)(?:在.{0,18})?(?:联系|更新|通知)(?:你|您)": "future contact is a promise; verify an owner or tracker",
    r"we(?:'ll| will) (?:contact|update|follow up with) you": "future contact is a promise; verify an owner or tracker",
    r"(?:they|someone|a teammate) will (?:take a look|follow up|reply|get back to you)(?:.{0,20})?(?:soon|shortly)": "future teammate follow-up and timing require a tracked owner and verified commitment",
    r"(?:会有|将由).{0,12}(?:同事|专人).{0,12}(?:尽快|很快|稍后).{0,8}(?:回复|跟进|联系)": "future teammate follow-up and timing require a tracked owner and verified commitment",
}

PROMISE_WARNINGS = {
    r"一定会": "unqualified promise",
    r"保证": "guarantee requires explicit authority",
    r"很快(?:上线|修复|解决)": "timeline requires an approved owner and date",
    r"definitely (?:fix|add|launch|support)": "unqualified promise",
    r"guarantee": "guarantee requires explicit authority",
    r"coming soon": "timeline requires an approved source",
    r"will be available soon": "timeline requires an approved source",
}

REPOSITORY_EVIDENCE_WARNINGS = {
    r"(?:下个|下一(?:个)?|未来).{0,10}(?:版本|更新).{0,10}(?:修复|解决)": "next-release claim requires verified Issue/PR state",
    r"(?:next|upcoming) (?:version|update)": "next-release claim requires verified Issue/PR state",
    r"(?:已经|已)(?:经)?修复": "fixed claim requires a merged PR and release-state verification",
    r"(?:has been|is) fixed": "fixed claim requires a merged PR and release-state verification",
}

PROHIBITED = {
    r"(?:低价值|没价值|薅羊毛|无意义)用户": "never label a customer by perceived worth",
    r"low[- ]value user": "never label a customer by perceived worth",
    r"as an AI": "do not expose internal drafting mechanics in a normal support reply",
    r"作为(?:一个)?AI": "do not expose internal drafting mechanics in a normal support reply",
    r"(?:Filo'?s?|Cursor'?s?)\s+AI Support Assistant": "do not use an AI-assistant signature in a normal support reply",
    r"(?:Filo|Cursor)[的 ]*AI\s*客服助手": "do not use an AI-assistant signature in a normal support reply",
    r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+": "do not expose private repository links; cite only Issue/PR numbers",
    r"\brelease[ -]?tag\b": "replace internal release terminology with released or waiting for release",
    r"(?<![#\w])tag(?![#\w])": "replace internal tag terminology with released or waiting for release",
    r"\bmerge commit\b": "do not expose merge-commit terminology to customers",
    r"\bhard rebuild\b": "replace internal implementation terminology with the visible customer symptom",
    r"\bstale cursor\b": "replace internal implementation terminology with the visible customer symptom",
    r"\bhistoryId\b": "do not expose internal synchronization identifiers to customers",
    r"发布标签": "replace internal release terminology with 已发布 or 已合并、等待发布",
    r"合并提交": "do not expose merge-commit terminology to customers",
    r"硬重建": "replace internal implementation terminology with the visible customer symptom",
    r"过期游标": "replace internal implementation terminology with the visible customer symptom",
}

ZH_CHARS = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_LETTERS = re.compile(r"[A-Za-z]")
LATIN_WORD = re.compile(r"[a-z0-9'-]+")
ECHO_CJK_MIN = 14
ECHO_WORD_MIN = 10
ECHO_MAX_REPORTED = 3


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def detect_language(text: str) -> str:
    cjk = len(ZH_CHARS.findall(text))
    latin = len(LATIN_LETTERS.findall(text))
    if cjk >= 4 and cjk >= max(4, int(latin * 0.18)):
        return "zh"
    if latin >= 8:
        return "en"
    return "zh" if cjk else "unknown"


def verbatim_echo_errors(reply: str, source: str) -> list[str]:
    """Reject drafts that replay the customer's own wording instead of summarizing.

    A confirmed Bug/Feature reply needs a one-sentence rephrased problem
    description, not an echo of the sender's clauses or detail lists. Long
    verbatim runs from the source (>= 14 CJK characters or >= 10 latin words)
    mean the draft is quoting the customer back at them. Short symptom phrases
    may reappear naturally and stay below the threshold.
    """

    errors: list[str] = []
    cjk_pattern = re.compile(rf"[㐀-䶿一-鿿]{{{ECHO_CJK_MIN},}}")
    for run in sorted(set(cjk_pattern.findall(source))):
        if run in reply:
            errors.append(f"reply echoes the customer's wording verbatim: {run[:30]!r}…; summarize in one rephrased sentence instead")
        if len(errors) >= ECHO_MAX_REPORTED:
            return errors

    source_words = LATIN_WORD.findall(source.lower())
    reply_joined = " " + " ".join(LATIN_WORD.findall(reply.lower())) + " "
    for start in range(len(source_words) - ECHO_WORD_MIN + 1):
        ngram = " " + " ".join(source_words[start : start + ECHO_WORD_MIN]) + " "
        if ngram in reply_joined:
            errors.append(
                "reply echoes the customer's wording verbatim: "
                f"{' '.join(source_words[start : start + ECHO_WORD_MIN])[:60]!r}…; "
                "summarize in one rephrased sentence instead"
            )
            if len(errors) >= ECHO_MAX_REPORTED:
                break
    return errors


def content_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    body = paragraphs[1:] if paragraphs and re.match(r"(?i)^hi\s", paragraphs[0]) else paragraphs
    body = [part for part in body if not re.match(r"(?i)^filo support\b", part)]
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", help="UTF-8 text file, or - for stdin")
    parser.add_argument("--anchor", action="append", default=[], help="specific detail expected in the reply; may be repeated")
    parser.add_argument("--category", choices=("bug", "feature", "other"), default="other", help="apply category-specific checks")
    parser.add_argument("--source-text", help="UTF-8 source-message text file used to enforce reply language")
    parser.add_argument("--source-language", choices=("zh", "en"), help="expected source-message language")
    parser.add_argument("--subject", help="draft subject used for reply-thread checks")
    args = parser.parse_args()

    try:
        text = read_text(args.draft)
    except (OSError, UnicodeError) as exc:
        print(f"[ERROR] cannot read draft: {exc}")
        return 2

    if not text.strip():
        print("[ERROR] draft is empty")
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    source_language = args.source_language
    source_text = ""
    if args.source_text:
        try:
            source_text = read_text(args.source_text)
        except (OSError, UnicodeError) as exc:
            print(f"[ERROR] cannot read source text: {exc}")
            return 2
        detected_source = detect_language(source_text)
        if source_language and detected_source not in {"unknown", source_language}:
            errors.append(
                f"declared source language {source_language!r} conflicts with detected {detected_source!r}"
            )
        if not source_language:
            source_language = detected_source

    reply_language = detect_language(text)
    if source_language in {"zh", "en"} and reply_language != source_language:
        errors.append(
            f"reply language {reply_language!r} does not match source language {source_language!r}"
        )

    if reply_language == "zh" and source_text:
        script_error = script_mismatch_error(source_text, text)
        if script_error:
            errors.append(script_error)

    # Chinese checks run on the Simplified-normalized draft so every
    # Simplified-written pattern also fires on Traditional replies.
    check_text = normalize_simplified(text)

    for pattern, message in PROHIBITED.items():
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            errors.append(f"{message}: /{pattern}/")
    for patterns in (PHRASE_WARNINGS, PROMISE_WARNINGS):
        for pattern, message in patterns.items():
            if re.search(pattern, check_text, flags=re.IGNORECASE):
                warnings.append(f"{message}: /{pattern}/")

    has_tracker_reference = bool(
        re.search(r"(?:Issue|PR)\s+(?:工单|ticket)\s*#\d+", check_text, flags=re.IGNORECASE)
    )
    language_for_tracker = source_language if source_language in {"zh", "en"} else reply_language
    if language_for_tracker == "zh":
        if re.search(r"\bIssue\s*#\d+", check_text, flags=re.IGNORECASE):
            errors.append("Chinese replies must use 'Issue 工单 #N', not bare 'Issue #N'")
        if re.search(r"\bPR\s*#\d+", check_text, flags=re.IGNORECASE):
            errors.append("Chinese replies must use 'PR 工单 #N', not bare 'PR #N'")
    elif language_for_tracker == "en":
        if re.search(r"\bIssue\s*#\d+", check_text, flags=re.IGNORECASE):
            errors.append("English replies must use 'Issue ticket #N', not bare 'Issue #N'")
        if re.search(r"\bPR\s*#\d+", check_text, flags=re.IGNORECASE):
            errors.append("English replies must use 'PR ticket #N', not bare 'PR #N'")
    for pattern, message in REPOSITORY_EVIDENCE_WARNINGS.items():
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            if args.category != "bug" or not has_tracker_reference:
                warnings.append(f"{message}: /{pattern}/")

    if check_text.count("理解") > 1:
        warnings.append("'理解' appears more than once; show understanding through specifics")
    if re.search(r"你提到的", check_text):
        warnings.append("'你提到的' replay pattern; rephrase the problem in one sentence instead of quoting the sender's details")
    if len(re.findall(r"\b(?:thank you|thanks)\b", text, flags=re.IGNORECASE)) > 2:
        warnings.append("thanks appears more than twice; reduce courtesy filler")
    if reply_language == "en" and len(re.findall(r"\bcurrently\b", text, flags=re.IGNORECASE)) > 1:
        warnings.append("'currently' appears more than once; turn verified facts into a natural reply instead of parallel status paragraphs")
    if check_text.count("抱歉") > 1 or len(re.findall(r"\b(?:sorry|apologi[sz]e)\b", check_text, flags=re.IGNORECASE)) > 1:
        warnings.append("multiple apologies may feel scripted or evasive")
    if re.search(r"^#{1,6}\s", text, flags=re.MULTILINE):
        warnings.append("outgoing email contains Markdown headings")
    if not re.match(r"^\s*Hi\s+[^,，\n]+[,，]", text, flags=re.IGNORECASE):
        warnings.append("reply should open with 'Hi <name>,' or 'Hi <name>，'")
    if re.search(r"\b(?:passed|handed|sent|forwarded) (?:this|it|your (?:request|case|issue)) to (?:a |the )?(?:teammate|specialist|team)\b", check_text, flags=re.IGNORECASE):
        warnings.append("teammate or specialist handoff must be backed by an actual routing, Issue, comment, or review record")
    if re.search(r"(?:已|已经)(?:转给|交给|转交给|提交给).{0,10}(?:同事|专人|团队)", check_text):
        warnings.append("teammate or specialist handoff must be backed by an actual routing, Issue, comment, or review record")

    if args.subject is not None and re.fullmatch(r"(?i)\s*re\s*:\s*", args.subject):
        errors.append("reply subject cannot be only 'Re:'")

    if args.source_text:
        errors.extend(verbatim_echo_errors(text, source_text))

    if args.category == "bug" and not has_tracker_reference:
        warnings.append("Bug reply must include a verified Issue/PR number")

    has_feature_reference = bool(
        re.search(r"Feature\s+(?:工单|ticket)\s*#\d+", check_text, flags=re.IGNORECASE)
    )
    if args.category == "feature" and not has_feature_reference:
        warnings.append("Feature reply must include a verified Feature ticket number")

    if args.category in {"bug", "feature"} and len(content_paragraphs(text)) > 4:
        warnings.append(
            "ticketed Bug/Feature reply should stay compact: confirm receipt, one "
            "rephrased problem sentence, ticket and status, thanks; do not re-enumerate details"
        )

    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    if len(text) > 1800 or word_count > 350:
        warnings.append(f"draft may be too long for support mail ({len(text)} characters, {word_count} word-like tokens)")

    for anchor in args.anchor:
        if anchor.casefold() not in text.casefold():
            warnings.append(f"expected specific detail is missing: {anchor!r}")

    for error in errors:
        print(f"[ERROR] {error}")
    for warning in warnings:
        print(f"[WARN] {warning}")

    if errors:
        return 2
    if warnings:
        return 1
    print("[OK] no deterministic voice or boundary warnings found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
