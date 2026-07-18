"""EJDict-hand(パブリックドメイン英和辞書)+ ユーザー辞書による単語引き。

ユーザー辞書 (data/user_dict.txt) は「見出し<TAB>意味」形式の平文で、
EJDict より優先される。ファイル更新は mtime で検知し再読込するので
アプリの再起動は不要。
"""
from __future__ import annotations

import sqlite3

from ..paths import DICT_DB, USER_DICT
from .base import Engine, EngineNotReady

USER_DICT_TEMPLATE = """\
# translator ユーザー辞書
# 書式: 見出し<TAB>意味   (タブ区切り、1行1見出し。# で始まる行は無視)
# EJDict より優先される。保存すれば即反映(アプリ再起動不要)。
pc\t〈C〉パソコン,パーソナルコンピュータ
"""


class DictionaryEngine(Engine):
    name = "dictionary"
    label = "辞書 (EJDict)"

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._user: dict[str, str] = {}
        self._user_mtime: float | None = None

    def _user_lookup(self, word: str) -> str | None:
        if not USER_DICT.exists():
            return None
        mtime = USER_DICT.stat().st_mtime
        if mtime != self._user_mtime:
            self._user = {}
            for line in USER_DICT.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or "\t" not in line:
                    continue
                head, meaning = line.split("\t", 1)
                self._user[head.strip().lower()] = meaning.strip()
            self._user_mtime = mtime
        return self._user.get(word)

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
        """単語を引く(ユーザー辞書優先)。見出しに無ければ語形変化を剥がして再試行。"""
        conn = self._connect()
        for candidate in self._candidates(word.lower()):
            prefix = "" if candidate == word.lower() else f"({candidate}) "
            user = self._user_lookup(candidate)
            if user is not None:
                return prefix + "・" + user.replace(" / ", "\n・")
            row = conn.execute(
                "SELECT meaning FROM entries WHERE word = ?", (candidate,)
            ).fetchone()
            if row:
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
