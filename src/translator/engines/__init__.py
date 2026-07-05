"""エンジンの遅延生成レジストリ。重いモデルは初回利用時にロードする。"""
from __future__ import annotations

from ..config import Config
from .base import Engine

_instances: dict[str, Engine] = {}


def get_engine(name: str, cfg: Config) -> Engine:
    if name in _instances:
        return _instances[name]
    if name == "dictionary":
        from .dictionary import DictionaryEngine
        engine: Engine = DictionaryEngine()
    elif name == "fugumt":
        from .fugumt import FuguMTEngine
        engine = FuguMTEngine()
    elif name == "plamo":
        from .plamo import PlamoEngine
        engine = PlamoEngine(cfg)
    elif name == "qwen_npu":
        from .qwen_npu import QwenNPUEngine
        engine = QwenNPUEngine(cfg)
    else:
        raise ValueError(f"unknown engine: {name}")
    _instances[name] = engine
    return engine


SENTENCE_ENGINES = ["fugumt", "plamo", "qwen_npu"]
