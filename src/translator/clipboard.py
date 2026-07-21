"""選択テキストの取得。クリップボードを退避 → Ctrl+C 送信 → 読み取り → 復元。"""
from __future__ import annotations

import time

import win32clipboard
import win32con


def _read_clipboard_text() -> str | None:
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.03)  # 他プロセスがクリップボードを掴んでいる
    return None


def _write_clipboard_text(text: str) -> None:
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.03)
    return


def read_copied_text() -> str | None:
    """double-ctrl-c モード用。ユーザー自身の Ctrl+C 直後に呼ばれるので、
    クリップボードが書き終わるのを少し待って読むだけでよい。"""
    text = None
    for _ in range(10):  # 最大 ~300ms
        text = _read_clipboard_text()
        if text:
            break
        time.sleep(0.03)
    return text.strip() if text else None


def grab_selection(hotkey_combo: str) -> str | None:
    """選択中テキストを返す。取得できなければ None。global モード専用
    (keyboard ライブラリで Ctrl+C を送出する)。"""
    import keyboard  # global モードでのみロード(none モードはフックを一切張らない)

    saved = _read_clipboard_text()

    # ホットキーの修飾キーが押されたままだと Ctrl+C が化けるので先に離す
    for key in hotkey_combo.split("+"):
        try:
            keyboard.release(key.strip())
        except Exception:
            pass
    time.sleep(0.05)

    # 検知用に一旦クリップボードを空にしてからコピーを送る
    _write_clipboard_text("")
    keyboard.send("ctrl+c")

    text = None
    for _ in range(20):  # 最大 ~600ms 待つ
        time.sleep(0.03)
        text = _read_clipboard_text()
        if text:
            break

    if saved is not None:
        _write_clipboard_text(saved)
    return text.strip() if text else None
