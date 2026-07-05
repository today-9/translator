"""EJDict-hand(パブリックドメイン英和辞書)による単語引き。"""
from __future__ import annotations

import sqlite3

from ..paths import DICT_DB
from .base import Engine, EngineNotReady


class DictionaryEngine(Engine):
    name = "dictionary"
    label = "辞書 (EJDict)"

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None

    def is_ready(self) -> bool:
        return DICT_DB.exists()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            if not DICT_DB.exists():
                raise EngineNotReady("辞書未構築。`uv run translator-setup dict` を実行してください")
            # ホットキーのワーカースレッドから呼ばれるため check_same_thread=False
            self._conn = sqlite3.connect(DICT_DB, check_same_thread=False)
        return self._conn

    def lookup(self, word: str) -> str | None:
        """単語を引く。見出しに無ければ簡単な語形変化を剥がして再試行。"""
        conn = self._connect()
        for candidate in self._candidates(word.lower()):
            row = conn.execute(
                "SELECT meaning FROM entries WHERE word = ?", (candidate,)
            ).fetchone()
            if row:
                prefix = "" if candidate == word.lower() else f"({candidate}) "
                return prefix + "・" + row[0].replace(" / ", "\n・")
        return None

    @staticmethod
    def _candidates(w: str) -> list[str]:
        cands = [w]
        # 規則変化の逆適用(雑だが実用上は十分)
        if w.endswith("ies") and len(w) > 4:
            cands.append(w[:-3] + "y")
        if w.endswith("es") and len(w) > 3:
            cands.append(w[:-2])
        if w.endswith("s") and len(w) > 2:
            cands.append(w[:-1])
        if w.endswith("ied") and len(w) > 4:
            cands.append(w[:-3] + "y")
        if w.endswith("ed") and len(w) > 3:
            cands.append(w[:-2])
            cands.append(w[:-1])          # loved -> love
            if len(w) > 4 and w[-3] == w[-4]:
                cands.append(w[:-3])      # stopped -> stop
        if w.endswith("ing") and len(w) > 4:
            cands.append(w[:-3])
            cands.append(w[:-3] + "e")    # making -> make
            if len(w) > 5 and w[-4] == w[-5]:
                cands.append(w[:-4])      # running -> run
        seen: set[str] = set()
        return [c for c in cands if not (c in seen or seen.add(c))]

    def translate(self, text: str) -> str:
        words = text.split()
        results = []
        for w in words:
            meaning = self.lookup(w)
            if meaning is None:
                results.append(f"{w}: (辞書に見出しなし)")
            else:
                results.append(f"{w}\n{meaning}" if len(words) > 1 else meaning)
        return "\n\n".join(results)
