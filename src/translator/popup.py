"""マウスカーソル近くに出す枠なしポップアップ。tkinter はメインスレッド専用なので、
表示要求は queue 経由で受け取り、メインループ側で処理する。"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import font as tkfont

import win32api

from .config import Config

_MONITOR_DEFAULTTONEAREST = 2


def _cursor_and_work_area() -> tuple[int, int, tuple[int, int, int, int]]:
    """カーソル座標と、カーソルがいるモニターの作業領域(タスクバー除く)。"""
    x, y = win32api.GetCursorPos()
    try:
        hmon = win32api.MonitorFromPoint((x, y), _MONITOR_DEFAULTTONEAREST)
        work = win32api.GetMonitorInfo(hmon)["Work"]  # (left, top, right, bottom)
    except Exception:
        work = (0, 0, 1920, 1080)
    return x, y, work

BG = "#1e1f22"
FG = "#e8e8e8"
ACCENT = "#8ab4f8"
SUB = "#9aa0a6"


class PopupManager:
    def __init__(self, root: tk.Tk, cfg: Config) -> None:
        self._root = root
        self._cfg = cfg
        self._queue: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._win: tk.Toplevel | None = None
        self._timeout_id: str | None = None
        self._mouse_hook = None
        self._esc_hook = None
        self._close_requested = threading.Event()
        self._poll()

    # ---- ワーカースレッドから呼ぶ API ----
    def show(self, body: str, header: str = "", footer: str = "") -> None:
        self._queue.put((body, header, footer))

    # ---- メインスレッド側 ----
    def _poll(self) -> None:
        # マウスフックのスレッドから直接 tk を触れないため、イベント経由で閉じる
        if self._close_requested.is_set():
            self._close_requested.clear()
            self._close()
        try:
            while True:
                body, header, footer = self._queue.get_nowait()
                self._show_now(body, header, footer)
        except queue.Empty:
            pass
        self._root.after(50, self._poll)

    def _unhook_mouse(self) -> None:
        if self._mouse_hook is not None:
            import mouse
            try:
                mouse.unhook(self._mouse_hook)
            except (ValueError, OSError):
                pass
            self._mouse_hook = None
        if self._esc_hook is not None:
            import keyboard
            try:
                keyboard.remove_hotkey(self._esc_hook)
            except (KeyError, ValueError):
                pass
            self._esc_hook = None

    def _close(self, _event=None) -> None:
        self._unhook_mouse()
        if self._timeout_id is not None:
            self._root.after_cancel(self._timeout_id)
            self._timeout_id = None
        if self._win is not None:
            self._win.destroy()
            self._win = None

    def _show_now(self, body: str, header: str, footer: str) -> None:
        self._close()
        self._close_requested.clear()  # 直前のクリック残留で即閉じないように
        cfg = self._cfg
        no_hook = cfg.hook_mode == "none"
        win = tk.Toplevel(self._root)
        self._win = win
        if no_hook:
            # フックを使わず Esc/クリックで閉じるにはフォーカスを持てる窓が必要。
            # overrideredirect の枠なし窓は Windows でフォーカスを取れないため、
            # 細いツールウィンドウ枠にする
            win.title("訳")
            win.attributes("-toolwindow", True)
        else:
            win.overrideredirect(True)
        win.attributes("-topmost", True)

        frame = tk.Frame(win, bg=BG, padx=12, pady=10,
                         highlightbackground="#3c4043", highlightthickness=1)
        frame.pack(fill="both", expand=True)

        base = tkfont.Font(family=cfg.font_family, size=cfg.font_size)
        small = tkfont.Font(family=cfg.font_family, size=max(cfg.font_size - 3, 8))

        if header:
            tk.Label(frame, text=header, bg=BG, fg=ACCENT, font=small,
                     anchor="w", justify="left",
                     wraplength=cfg.popup_max_width).pack(fill="x")
        tk.Label(frame, text=body, bg=BG, fg=FG, font=base,
                 anchor="w", justify="left",
                 wraplength=cfg.popup_max_width).pack(fill="x", pady=(2, 0))
        if footer:
            tk.Label(frame, text=footer, bg=BG, fg=SUB, font=small,
                     anchor="e", justify="right",
                     wraplength=cfg.popup_max_width).pack(fill="x", pady=(4, 0))

        # カーソルがいるモニターの作業領域内に収める(マルチモニター対応。
        # プライマリの幅でクランプするとサブモニターの訳がメインに飛ぶ)
        win.update_idletasks()
        x, y, (left, top, right, bottom) = _cursor_and_work_area()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = max(min(x + 16, right - w - 8), left)
        y = max(min(y + 16, bottom - h - 8), top)
        win.geometry(f"+{x}+{y}")

        win.bind("<Escape>", self._close)
        win.bind("<Button-1>", self._close)
        if no_hook:
            # フックなし: 窓自身にフォーカスを当て、Esc(窓バインド)と
            # FocusOut(他所をクリック)で閉じる。グローバル監視はしない
            win.bind("<FocusOut>", self._close)
            win.focus_force()
        else:
            # 画面のどこをクリックしても・Esc でも閉じる(タイムアウトは保険)。
            # ポップアップはフォーカスを奪わない設計のため、表示中だけ
            # グローバルフックで受ける。suppress しないので前面アプリの
            # Esc 動作はそのまま
            import keyboard
            import mouse
            self._mouse_hook = mouse.on_button(
                self._close_requested.set, buttons=("left", "right"), types=("down",)
            )
            self._esc_hook = keyboard.add_hotkey(
                "esc", self._close_requested.set, suppress=False
            )
        self._timeout_id = self._root.after(cfg.popup_timeout_ms, self._close)
