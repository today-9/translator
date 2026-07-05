"""FuguMT (staka/fugumt-en-ja) を CTranslate2 int8 で実行する文章翻訳エンジン。"""
from __future__ import annotations

import re
import threading

from ..paths import FUGUMT_DIR
from .base import Engine, EngineNotReady

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


class FuguMTEngine(Engine):
    name = "fugumt"
    label = "FuguMT (CPU)"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._translator = None
        self._sp_src = None
        self._sp_tgt = None

    def is_ready(self) -> bool:
        return (FUGUMT_DIR / "model.bin").exists()

    def warmup(self) -> None:
        with self._lock:
            self._load()

    def _load(self) -> None:
        if self._translator is not None:
            return
        if not self.is_ready():
            raise EngineNotReady("FuguMT未配置。`uv run translator-setup fugumt` を実行してください")
        import ctranslate2
        import sentencepiece as spm

        self._translator = ctranslate2.Translator(
            str(FUGUMT_DIR), device="cpu", compute_type="int8"
        )
        self._sp_src = spm.SentencePieceProcessor(str(FUGUMT_DIR / "source.spm"))
        self._sp_tgt = spm.SentencePieceProcessor(str(FUGUMT_DIR / "target.spm"))

    def translate(self, text: str) -> str:
        with self._lock:
            self._load()
            out_lines = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                sentences = _SENT_SPLIT.split(line)
                # Marian系は入力末尾に EOS が必須。無いと出力が繰り返し暴走する
                tokens = [
                    self._sp_src.encode(s, out_type=str) + ["</s>"]
                    for s in sentences
                ]
                results = self._translator.translate_batch(
                    tokens, beam_size=4, max_decoding_length=512
                )
                decoded = [
                    self._sp_tgt.decode([t for t in r.hypotheses[0]])
                    for r in results
                ]
                out_lines.append("".join(decoded))
            return "\n".join(out_lines)
