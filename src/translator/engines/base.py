from __future__ import annotations

from abc import ABC, abstractmethod


class EngineNotReady(Exception):
    """モデル未ダウンロードなど、セットアップ不足で使えない状態。"""


class Engine(ABC):
    name: str = "base"
    label: str = "base"  # ポップアップに出す表示名

    @abstractmethod
    def translate(self, text: str) -> str:
        """英語テキストを日本語に翻訳して返す。"""

    def warmup(self) -> None:
        """モデルロード等の事前準備(任意)。"""

    def is_ready(self) -> bool:
        """必要なモデル・データが配置済みか。"""
        return True
