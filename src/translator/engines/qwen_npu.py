"""Qwen3-4B (int4/OpenVINO) を NPU で実行する翻訳エンジン。

NPUで載らない場合は GPU -> CPU の順にフォールバックする。
"""
from __future__ import annotations

import re
import threading

from ..config import Config
from ..paths import DATA_DIR, QWEN_OV_DIR
from .base import Engine, EngineNotReady

SYSTEM_PROMPT = (
    "You are a professional English-to-Japanese translator. "
    "Translate the user's text into natural Japanese. "
    "Output ONLY the Japanese translation, no explanations."
)

# Qwen3-Instruct-2507 は思考モードなしの ChatML
PROMPT_TEMPLATE = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{text}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class QwenNPUEngine(Engine):
    name = "qwen_npu"
    label = "Qwen3-4B-Instruct"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._pipe = None
        self.device: str | None = None  # 実際にロードされたデバイス

    def is_ready(self) -> bool:
        return (QWEN_OV_DIR / "openvino_model.xml").exists() and (QWEN_OV_DIR / "openvino_model.bin").exists()

    def warmup(self) -> None:
        with self._lock:
            self._load()

    def _load(self) -> None:
        if self._pipe is not None:
            return
        if not self.is_ready():
            raise EngineNotReady("Qwenモデル未配置。`uv run translator-setup qwen` を実行してください")
        import openvino_genai

        cache_dir = DATA_DIR / "ov_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        errors = []
        for device in self._cfg.qwen_devices:
            try:
                # CACHE_DIR: コンパイル済みブロブを保存し、2回目以降のロードを短縮する
                self._pipe = openvino_genai.LLMPipeline(
                    str(QWEN_OV_DIR), device, CACHE_DIR=str(cache_dir)
                )
                self.device = device
                self.label = f"Qwen3-4B ({device})"
                return
            except Exception as e:  # デバイス非対応・メモリ不足など
                errors.append(f"{device}: {e}")
        raise RuntimeError("全デバイスでロード失敗:\n" + "\n".join(errors))

    def translate(self, text: str) -> str:
        with self._lock:
            self._load()
            import openvino_genai

            gen_cfg = openvino_genai.GenerationConfig()
            gen_cfg.max_new_tokens = self._cfg.qwen_max_new_tokens
            gen_cfg.do_sample = False
            # 自前で ChatML を組んでいるので、GenAI 側のテンプレート適用は切る
            gen_cfg.apply_chat_template = False
            prompt = PROMPT_TEMPLATE.format(system=SYSTEM_PROMPT, text=text)
            out = self._pipe.generate(prompt, gen_cfg)
            out = _THINK_RE.sub("", str(out))
            return out.strip()
