"""RegisterHotKey ベースのグローバルホットキー(フックなし)。

keyboard ライブラリの低レベルフック(SetWindowsHookEx)は全キー入力を傍受
するため、EDR にキーロガーとして検知される。RegisterHotKey は「特定の
キー組み合わせだけを OS に予約する」方式で、他アプリの入力は一切覗かない
ので、その検知ヒューリスティックには引っかからない。

RegisterHotKey のメッセージは登録したスレッドのキューに届くため、専用
スレッドでメッセージループを回す。
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_MOD = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002,
        "shift": 0x0004, "win": 0x0008, "windows": 0x0008}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012

# 単一キー名 → 仮想キーコード
_VK = {chr(c): c for c in range(0x30, 0x5B)}  # 0-9, A-Z (大文字)
_VK.update({f"f{i}": 0x70 + (i - 1) for i in range(1, 13)})  # F1-F12
_VK.update({"space": 0x20, "enter": 0x0D, "tab": 0x09,
            "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23})


class HotkeyError(ValueError):
    pass


def parse_combo(combo: str) -> tuple[int, int]:
    """"ctrl+alt+c" → (修飾フラグ, 仮想キーコード)。"""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise HotkeyError(f"空のホットキー: {combo!r}")
    *mods, key = parts
    mod_flags = 0
    for m in mods:
        if m not in _MOD:
            raise HotkeyError(f"不明な修飾キー: {m!r} ({combo!r})")
        mod_flags |= _MOD[m]
    vk = _VK.get(key.upper()) if len(key) == 1 else _VK.get(key)
    if vk is None:
        raise HotkeyError(f"未対応のキー: {key!r} ({combo!r})")
    return mod_flags, vk


class HotkeyListener:
    """RegisterHotKey を専用スレッドで待ち受ける。フックは張らない。"""

    def __init__(self) -> None:
        self._specs: list[tuple[int, int, int, str]] = []  # (id, mod, vk, combo)
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._tid: int | None = None
        self._ready = threading.Event()
        self._failures: list[str] = []

    def add(self, combo: str, callback: Callable[[], None]) -> None:
        hid = len(self._specs) + 1
        mod, vk = parse_combo(combo)
        self._specs.append((hid, mod, vk, combo))
        self._callbacks[hid] = callback

    def start(self) -> list[str]:
        """メッセージループを開始。登録に失敗した組み合わせのリストを返す。"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        return self._failures

    def _run(self) -> None:
        self._tid = _kernel32.GetCurrentThreadId()
        for hid, mod, vk, combo in self._specs:
            if not _user32.RegisterHotKey(None, hid, mod | _MOD_NOREPEAT, vk):
                # 他アプリが同じ組み合わせを既に握っている等
                self._failures.append(combo)
        self._ready.set()

        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY:
                cb = self._callbacks.get(msg.wParam)
                if cb is not None:
                    threading.Thread(target=cb, daemon=True).start()
        for hid, *_ in self._specs:
            _user32.UnregisterHotKey(None, hid)

    def stop(self) -> None:
        if self._tid is not None:
            _user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            self._tid = None
