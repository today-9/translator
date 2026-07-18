"""config.toml の読み込み。無ければデフォルトを生成する。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

from .paths import CONFIG_PATH

DEFAULT_CONFIG = """\
# translator 設定ファイル

[hotkey]
# "double-ctrl-c" = Ctrl+C 2連打で翻訳(推奨。他アプリと衝突しない)
# または keyboard ライブラリの書式で組み合わせ指定。例: "ctrl+alt+t", "f9"
combo = "double-ctrl-c"
# 2連打と判定する間隔 (ミリ秒)
double_press_ms = 500
# 手入力翻訳の小窓を開くホットキー。空文字 "" で無効化
input_combo = "ctrl+alt+t"

[engine]
# 文章翻訳に使うエンジン: "fugumt" | "plamo" | "qwen_npu"
sentence = "fugumt"

[popup]
timeout_ms = 15000
font_family = "Yu Gothic UI"
font_size = 11
max_width = 480

[plamo]
port = 8765
# GPU レイヤ数。PLaMo (Mamba系) は Vulkan/iGPU だと壊れる+遅いので 0 (CPU) が正解
n_gpu_layers = 0
ctx_size = 4096
# アプリ起動時にサーバーも起動しておく(初回翻訳を速くする。メモリは常時 ~6GB 消費)
preload = false

[qwen]
# 実行デバイス。先頭から順に試す。実測: GPU 0.5-2.0秒 / CPU 1.2-3.8秒 / NPU 4.1-9.6秒
# NPU は最遅だが CPU/GPU を占有しないので、ゲーム中・重い作業中はNPU先頭も選択肢
devices = ["GPU", "NPU", "CPU"]
max_new_tokens = 512
preload = false
"""


@dataclass
class Config:
    hotkey: str = "double-ctrl-c"
    double_press_ms: int = 500
    input_combo: str = "ctrl+alt+t"
    sentence_engine: str = "fugumt"
    popup_timeout_ms: int = 15000
    font_family: str = "Yu Gothic UI"
    font_size: int = 11
    popup_max_width: int = 480
    plamo_port: int = 8765
    plamo_n_gpu_layers: int = 0
    plamo_ctx_size: int = 4096
    plamo_preload: bool = False
    qwen_devices: list[str] = field(default_factory=lambda: ["GPU", "NPU", "CPU"])
    qwen_max_new_tokens: int = 512
    qwen_preload: bool = False


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(DEFAULT_CONFIG, encoding="utf-8")
    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg = Config()
    hotkey = raw.get("hotkey", {})
    cfg.hotkey = hotkey.get("combo", cfg.hotkey)
    cfg.double_press_ms = hotkey.get("double_press_ms", cfg.double_press_ms)
    cfg.input_combo = hotkey.get("input_combo", cfg.input_combo)
    engine = raw.get("engine", {})
    cfg.sentence_engine = engine.get("sentence", cfg.sentence_engine)
    popup = raw.get("popup", {})
    cfg.popup_timeout_ms = popup.get("timeout_ms", cfg.popup_timeout_ms)
    cfg.font_family = popup.get("font_family", cfg.font_family)
    cfg.font_size = popup.get("font_size", cfg.font_size)
    cfg.popup_max_width = popup.get("max_width", cfg.popup_max_width)
    plamo = raw.get("plamo", {})
    cfg.plamo_port = plamo.get("port", cfg.plamo_port)
    cfg.plamo_n_gpu_layers = plamo.get("n_gpu_layers", cfg.plamo_n_gpu_layers)
    cfg.plamo_ctx_size = plamo.get("ctx_size", cfg.plamo_ctx_size)
    cfg.plamo_preload = plamo.get("preload", cfg.plamo_preload)
    qwen = raw.get("qwen", {})
    cfg.qwen_devices = qwen.get("devices", cfg.qwen_devices)
    cfg.qwen_max_new_tokens = qwen.get("max_new_tokens", cfg.qwen_max_new_tokens)
    cfg.qwen_preload = qwen.get("preload", cfg.qwen_preload)
    return cfg
