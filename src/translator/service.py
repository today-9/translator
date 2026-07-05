"""入力テキスト → エンジン選択 → 翻訳結果、のルーティング。"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Config
from .detect import is_dictionary_candidate, is_japanese, normalize
from .engines import get_engine


@dataclass
class TranslationResult:
    text: str          # 訳文
    engine_label: str  # 表示用エンジン名
    elapsed: float     # 秒


def translate(raw_text: str, cfg: Config, engine_name: str | None = None) -> TranslationResult:
    """engine_name 指定時は判定を飛ばしてそのエンジンを使う(ベンチ・CLI用)。"""
    text = normalize(raw_text)
    start = time.perf_counter()

    if not text:
        return TranslationResult("(テキストが取得できませんでした)", "-", 0.0)
    if is_japanese(text):
        return TranslationResult("(日本語のテキストです。このツールは英→日専用です)", "-", 0.0)

    if engine_name is None:
        if is_dictionary_candidate(text):
            dic = get_engine("dictionary", cfg)
            if dic.is_ready():
                result = dic.translate(text)
                if "辞書に見出しなし" not in result:
                    return TranslationResult(result, dic.label, time.perf_counter() - start)
            # 辞書に無い語は機械翻訳へフォールバック
        engine_name = cfg.sentence_engine

    engine = get_engine(engine_name, cfg)
    result = engine.translate(text)
    return TranslationResult(result, engine.label, time.perf_counter() - start)
