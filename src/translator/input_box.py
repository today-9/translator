"""手入力翻訳用の小窓。ホットキー/トレイメニューから開き、Enterで翻訳する。

tkinter はメインスレッド専用のため、表示要求は Event 経由で受け取り
メインループ側(_poll)で処理する。
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from .config import Config
from .popup import BG, FG, SUB, _cursor_and_work_area


class InputBox:
    def __init__(self, root: tk.Tk, cfg: Config,
                 on_submit: Callable[[str], None]) -> None:
        self._root = root
        self._cfg = cfg
        self._on_submit = on_submit  # ワーカースレッドで呼ばれる
        self._requested = threading.Event()
        self._win: tk.Toplevel | None = None
        self._entry: tk.Entry | None = None
        self._poll()

    # ---- 任意のスレッドから呼べる ----
    def ask(self) -> None:
        self._requested.set()

    # ---- メインスレッド側 ----
    def _poll(self) -> None:
        if self._requested.is_set():
            self._requested.clear()
            self._show()
        self._root.after(50, self._poll)

    def _close(self, _event=None) -> None:
        if self._win is not None:
            self._win.destroy()
            self._win = None
            self._entry = None

    def _submit(self, _event=None) -> None:
        text = self._entry.get().strip() if self._entry else ""
        self._close()
        if text:
            threading.Thread(target=self._on_submit, args=(text,), daemon=True).start()

    def _show(self) -> None:
        self._close()
        cfg = self._cfg
        win = tk.Toplevel(self._root)
        self._win = win
        win.title("翻訳 - 入力")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        frame = tk.Frame(win, bg=BG, padx=10, pady=8)
        frame.pack(fill="both", expand=True)
        base = tkfont.Font(family=cfg.font_family, size=cfg.font_size)
        small = tkfont.Font(family=cfg.font_family, size=max(cfg.font_size - 3, 8))

        tk.Label(frame, text="Enter=翻訳 / Esc=閉じる", bg=BG, fg=SUB,
                 font=small, anchor="w").pack(fill="x")
        entry = tk.Entry(frame, width=48, font=base, bg="#2b2d30", fg=FG,
                         insertbackground=FG, relief="flat")
        entry.pack(fill="x", pady=(4, 0), ipady=4)
        self._entry = entry

        # カーソルがいるモニター内に配置
        win.update_idletasks()
        x, y, (left, top, right, bottom) = _cursor_and_work_area()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = max(min(x + 16, right - w - 8), left)
        y = max(min(y + 16, bottom - h - 8), top)
        win.geometry(f"+{x}+{y}")

        entry.bind("<Return>", self._submit)
        entry.bind("<KP_Enter>", self._submit)
        # Esc はフォーカスを持つ Entry 側にも直接バインドする
        # (Toplevel 側のバインドだけだと届かない環境がある)
        entry.bind("<Escape>", self._close)
        win.bind("<Escape>", self._close)
        win.protocol("WM_DELETE_WINDOW", self._close)
        win.lift()
        entry.focus_force()
