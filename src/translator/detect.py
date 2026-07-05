"""入力テキストの種別判定。"""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]*$")
_JA_RE = re.compile(r"[぀-ヿ一-鿿]")


def normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def is_japanese(text: str) -> bool:
    """日本語文字が過半なら True(EN->JA 専用ツールなので対象外扱い)。"""
    ja = len(_JA_RE.findall(text))
    return ja > 0 and ja >= len(text) * 0.3


def is_dictionary_candidate(text: str) -> bool:
    """辞書引きを先に試すべき入力か(英単語1〜3語)。"""
    words = normalize(text).split()
    return 0 < len(words) <= 3 and all(_WORD_RE.match(w) for w in words)
