#!/usr/bin/env python3
"""Simplified/Traditional Chinese script helpers for reply-language matching.

Replies must follow the customer's Chinese script: Simplified customers get
简体, Traditional customers get 繁體. These helpers classify a text's script
from characters unique to one script and normalize Traditional text so the
shared Simplified-only regex checks keep working on Traditional drafts.
"""

from __future__ import annotations


# Simplified/Traditional pairs, simplified first. Entries whose simplified
# side also exists in Traditional (于后划复户么系里) are translation-only and
# are excluded from the classification evidence by AMBIGUOUS_SIMPLIFIED.
_PAIRS = (
    # core vocabulary of support mail
    "们們", "见見", "设設", "开開", "关關", "闭閉", "门門", "问問", "时時",
    "无無", "这這", "对對", "点點", "击擊", "选選", "择擇", "确確", "删刪",
    "讯訊", "传傳", "数數", "网網", "练練", "线線", "简簡", "体體", "号號",
    "标標", "签簽", "签籤", "账帳", "邮郵", "边邊", "键鍵", "盘盤", "寻尋",
    "题題", "处處", "张張", "单單", "记記", "录錄", "为為", "与與", "译譯",
    "语語", "谢謝", "该該", "详詳", "细細", "复復", "复複", "应應", "当當",
    "请請", "个個", "来來", "过過", "还還", "让讓", "办辦", "连連", "给給",
    "从從", "东東", "华華", "资資", "务務", "业業", "电電", "转轉", "备備",
    "类類", "种種", "样樣", "档檔", "错錯", "订訂", "阅閱", "读讀", "写寫",
    "输輸", "经經", "联聯", "统統", "贴貼", "图圖", "试試", "测測", "软軟",
    "难難", "欢歡", "银銀", "双雙", "湾灣", "货貨", "币幣", "购購", "费費",
    "发發", "验驗", "证證", "码碼", "间間", "现現", "页頁", "视視", "频頻",
    "夹夾", "帮幫", "响響", "级級", "执執", "万萬", "载載", "报報", "馈饋",
    "览覽", "会會",
    # extended common vocabulary
    "众眾", "优優", "觉覺", "讲講", "论論", "访訪", "评評", "识識", "诉訴",
    "认認", "负負", "责責", "贵貴", "买買", "达達", "运運", "进進", "适適",
    "递遞", "随隨", "隐隱", "云雲", "项項", "须須", "状狀", "态態", "调調",
    "谁誰", "话話", "询詢", "环環", "动動", "换換", "显顯", "创創", "编編",
    "辑輯", "败敗", "尽盡", "尽儘", "装裝", "启啟", "扩擴", "浏瀏", "链鏈",
    "悬懸", "钮鈕", "权權", "风風", "险險", "续續", "绑綁", "国國", "陆陸",
    "马馬", "亚亞", "团團", "队隊", "长長", "锁鎖", "远遠", "逻邏", "组組",
    "织織", "审審", "计計", "获獲", "结結", "义義", "历歷", "实實", "满滿",
    "区區", "术術", "专專", "宝寶", "带帶", "谅諒", "将將", "决決", "并併",
    "机機", "脑腦", "别別", "销銷", "顶頂", "顺順", "额額", "两兩", "准準",
    "发髮", "划劃",
    # translation-only pairs: the simplified side also exists in Traditional
    "里裡", "于於", "么麼", "系繫", "系係", "户戶", "后後", "复覆",
)

TRAD_TO_SIMP = {pair[1]: pair[0] for pair in _PAIRS}

# Simplified characters that are also valid Traditional must not count as
# Simplified evidence when classifying a text.
AMBIGUOUS_SIMPLIFIED = frozenset("于后划复户么系里")

SCRIPT_ONLY_TRADITIONAL = frozenset(TRAD_TO_SIMP)
SCRIPT_ONLY_SIMPLIFIED = frozenset(TRAD_TO_SIMP.values()) - AMBIGUOUS_SIMPLIFIED

_SCRIPT_LABELS = {"hans": "Simplified (简体)", "hant": "Traditional (繁體)"}

_TRANSLATE_TABLE = str.maketrans(TRAD_TO_SIMP)


def chinese_script(text: str) -> str:
    """Classify Chinese text as 'hans', 'hant', or 'unknown'.

    Only characters unique to one script count, and classification needs at
    least two unique hits dominating the other script by more than 2:1, so
    short or mixed-script texts stay 'unknown' instead of guessing.
    """
    trad = sum(text.count(char) for char in SCRIPT_ONLY_TRADITIONAL)
    simp = sum(text.count(char) for char in SCRIPT_ONLY_SIMPLIFIED)
    if trad >= 2 and trad > simp * 2:
        return "hant"
    if simp >= 2 and simp > trad * 2:
        return "hans"
    return "unknown"


def script_label(script: str) -> str:
    return _SCRIPT_LABELS.get(script, "unknown")


def normalize_simplified(text: str) -> str:
    """Map Traditional-only characters to their Simplified forms.

    Deterministic voice/boundary regexes are written in Simplified Chinese;
    normalizing Traditional drafts lets every check apply to both scripts
    without weakening any pattern.
    """
    return text.translate(_TRANSLATE_TABLE)


def script_mismatch_error(source: str, reply: str) -> str | None:
    """Return the reply-script error message, or None when the scripts agree."""
    source_script = chinese_script(source)
    reply_script = chinese_script(reply)
    if (
        source_script in _SCRIPT_LABELS
        and reply_script in _SCRIPT_LABELS
        and source_script != reply_script
    ):
        return (
            "reply is written in "
            f"{script_label(reply_script)} Chinese but the customer wrote "
            f"{script_label(source_script)} Chinese; "
            "rewrite the reply in the customer's script"
        )
    return None
