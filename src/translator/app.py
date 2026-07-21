"""常駐アプリ本体: トレイ + グローバルホットキー + ポップアップ。"""
from __future__ import annotations

import threading
import tkinter as tk

import pystray
import win32api
from PIL import Image, ImageDraw, ImageFont

from .clipboard import grab_selection, read_copied_text
from .config import Config, load_config
from .engines import SENTENCE_ENGINES, get_engine
from .engines.base import EngineNotReady
from .input_box import InputBox
from .popup import PopupManager
from .service import translate

# none モードで "double-ctrl-c" が指定されていたときの代替(2連打はフックなしでは不可)
_NONE_MODE_DEFAULT_COMBO = "ctrl+alt+c"


# keyboard ライブラリは修飾キーの key-up を取りこぼすと「押しっぱなし」と
# 誤認し、以後 t 単体で ctrl+alt+t が発火する。OS の実キー状態で二重確認する
_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "windows": 0x5B}


def _modifiers_really_down(combo: str) -> bool:
    mods = [p.strip().lower() for p in combo.split("+")[:-1]]
    return all(
        bool(win32api.GetAsyncKeyState(_VK[m]) & 0x8000)
        for m in mods if m in _VK
    )


def _tray_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (30, 31, 34, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 59, 59], radius=12, outline=(138, 180, 248, 255), width=4)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/YuGothB.ttc", 40)
        d.text((12, 8), "訳", fill=(232, 232, 232, 255), font=font)
    except OSError:
        d.text((24, 20), "T", fill=(232, 232, 232, 255))
    return img


class App:
    def __init__(self) -> None:
        self.cfg: Config = load_config()
        self.paused = False
        self._busy = threading.Lock()
        self._last_ctrl_c = 0.0
        # インストール済みの文章エンジンのみメニューに出す(PLaMo抜き構成対応)
        self.available_engines = [
            n for n in SENTENCE_ENGINES if get_engine(n, self.cfg).is_ready()
        ]
        if self.cfg.sentence_engine not in self.available_engines:
            fallback = self.available_engines[0] if self.available_engines else "fugumt"
            self.cfg.sentence_engine = fallback
        self.root = tk.Tk()
        self.root.withdraw()
        self.popup = PopupManager(self.root, self.cfg)
        self.input_box = InputBox(self.root, self.cfg, self._translate_and_show)
        self.tray: pystray.Icon | None = None
        self._listener = None  # none モードの RegisterHotKey リスナー

    # ---- ホットキー処理(keyboard のスレッドから呼ばれる)----
    def on_hotkey(self) -> None:
        if self.paused:
            return
        if not self._busy.acquire(blocking=False):
            return  # 前の翻訳が実行中
        threading.Thread(target=self._capture_and_translate, daemon=True).start()

    def on_ctrl_c(self) -> None:
        """double-ctrl-c モード: 規定時間内の2回目の Ctrl+C で発火。"""
        import time as _time

        if not _modifiers_really_down("ctrl+c"):
            return  # Ctrl が実際には押されていない誤発火
        now = _time.monotonic()
        is_double = (now - self._last_ctrl_c) * 1000 <= self.cfg.double_press_ms
        self._last_ctrl_c = now
        if is_double:
            self._last_ctrl_c = 0.0  # 3連打で2回発火しないようリセット
            self.on_hotkey()

    def on_clipboard_hotkey(self) -> None:
        """none モード: 現在のクリップボード内容を翻訳する(コピー後にホットキー)。"""
        if self.paused:
            return
        if not self._busy.acquire(blocking=False):
            return
        try:
            text = read_copied_text()
            if not text:
                self.popup.show("(クリップボードが空です。コピーしてからどうぞ)",
                                header="translator")
                return
            self._translate_and_show(text, locked=True)
        finally:
            self._busy.release()

    def _capture_and_translate(self) -> None:
        try:
            if self.cfg.hotkey == "double-ctrl-c":
                text = read_copied_text()  # ユーザーが自分でコピー済み
            else:
                text = grab_selection(self.cfg.hotkey)
            if not text:
                self.popup.show("(選択テキストを取得できませんでした)", header="translator")
                return
            self._translate_and_show(text, locked=True)
        finally:
            self._busy.release()

    def _translate_and_show(self, text: str, locked: bool = False) -> None:
        """テキストを翻訳してポップアップ表示する(手入力・選択の共通経路)。"""
        if not locked and not self._busy.acquire(blocking=False):
            return
        try:
            preview = text if len(text) <= 60 else text[:57] + "..."
            if self.cfg.sentence_engine in ("plamo", "qwen_npu"):
                self.popup.show("翻訳中...", header=preview)
            result = translate(text, self.cfg)
            self.popup.show(
                result.text,
                header=preview,
                footer=f"{result.engine_label} / {result.elapsed:.2f}s",
            )
        except EngineNotReady as e:
            self.popup.show(str(e), header="セットアップが必要です")
        except Exception as e:
            self.popup.show(f"エラー: {e}", header="translator")
        finally:
            if not locked:
                self._busy.release()

    # ---- トレイメニュー ----
    def _menu(self) -> pystray.Menu:
        def set_engine(name: str):
            def handler(icon, item):
                self.cfg.sentence_engine = name
            return handler

        def is_engine(name: str):
            return lambda item: self.cfg.sentence_engine == name

        def toggle_pause(icon, item):
            self.paused = not self.paused

        engine_items = [
            pystray.MenuItem(
                {"fugumt": "FuguMT (速い)", "plamo": "PLaMo翻訳 (高品質/CPU)",
                 "qwen_npu": "Qwen3-4B (LLM)"}[n],
                set_engine(n), checked=is_engine(n), radio=True)
            for n in self.available_engines
        ]
        if self.cfg.hook_mode == "none":
            hotkey_label = self._selection_combo()
        else:
            hotkey_label = ("Ctrl+C ×2" if self.cfg.hotkey == "double-ctrl-c"
                            else self.cfg.hotkey)
        return pystray.Menu(
            pystray.MenuItem(f"ホットキー: {hotkey_label}", None, enabled=False),
            # 既定アクション(トレイ左クリック)= 入力窓。none モードでフックなしでも開ける
            pystray.MenuItem("入力して翻訳...",
                             lambda icon, item: self.input_box.ask(), default=True),
            pystray.Menu.SEPARATOR,
            *engine_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("一時停止", toggle_pause, checked=lambda i: self.paused),
            pystray.MenuItem("終了", self._quit),
        )

    def _quit(self, icon=None, item=None) -> None:
        try:
            plamo = get_engine("plamo", self.cfg)
            if hasattr(plamo, "shutdown"):
                plamo.shutdown()
        except Exception:
            pass
        if self.tray is not None:
            self.tray.stop()
        if self._listener is not None:
            self._listener.stop()
        else:
            import keyboard
            keyboard.unhook_all()
        self.root.after(0, self.root.destroy)

    def _selection_combo(self) -> str:
        """none モードの選択翻訳ホットキー。2連打指定なら組み合わせに置換。"""
        if self.cfg.hotkey in ("double-ctrl-c", ""):
            return _NONE_MODE_DEFAULT_COMBO
        return self.cfg.hotkey

    def _register_hotkeys_global(self) -> None:
        import keyboard  # 低レベルフックをここでロード(EDR に検知され得る)
        if self.cfg.hotkey == "double-ctrl-c":
            keyboard.add_hotkey("ctrl+c", self.on_ctrl_c, suppress=False)
        else:
            keyboard.add_hotkey(self.cfg.hotkey, self.on_hotkey, suppress=False)
        if self.cfg.input_combo:
            def on_input_hotkey() -> None:
                if _modifiers_really_down(self.cfg.input_combo):
                    self.input_box.ask()
            keyboard.add_hotkey(self.cfg.input_combo,
                                on_input_hotkey, suppress=False)

    def _register_hotkeys_nohook(self) -> None:
        from .hotkeys import HotkeyError, HotkeyListener

        listener = HotkeyListener()
        try:
            listener.add(self._selection_combo(), self.on_clipboard_hotkey)
            if self.cfg.input_combo:
                listener.add(self.cfg.input_combo, self.input_box.ask)
        except HotkeyError as e:
            self.popup.show(f"ホットキー設定エラー: {e}", header="translator")
        failures = listener.start()
        self._listener = listener
        if failures:
            self.popup.show(
                "次のホットキーは他アプリが使用中で登録できませんでした:\n"
                + ", ".join(failures) + "\nトレイの左クリックからも翻訳できます",
                header="translator")

    # ---- 起動 ----
    def run(self) -> None:
        if self.cfg.hook_mode == "none":
            self._register_hotkeys_nohook()
        else:
            self._register_hotkeys_global()

        self.tray = pystray.Icon("translator", _tray_icon_image(), "translator", self._menu())
        threading.Thread(target=self.tray.run, daemon=True).start()

        # 事前ロード指定があれば裏で温める
        def preload():
            try:
                if self.cfg.plamo_preload:
                    get_engine("plamo", self.cfg).warmup()
                if self.cfg.qwen_preload:
                    get_engine("qwen_npu", self.cfg).warmup()
                if self.cfg.sentence_engine == "fugumt":
                    get_engine("fugumt", self.cfg).warmup()
            except Exception:
                pass
        threading.Thread(target=preload, daemon=True).start()

        if self.cfg.hook_mode == "none":
            hint = (f"コピー後 {self._selection_combo()} で翻訳 / "
                    f"{self.cfg.input_combo or 'トレイ左クリック'} で入力窓")
        elif self.cfg.hotkey == "double-ctrl-c":
            hint = "テキストを選択して Ctrl+C を2連打で翻訳します"
        else:
            hint = f"テキストを選択して {self.cfg.hotkey} で翻訳します"
        self.popup.show(f"起動しました。{hint}", header="translator")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._quit()


def main() -> None:
    # 多重起動ガード(2つ動くとホットキーが二重発火する)
    import win32api
    import win32event
    import winerror

    mutex = win32event.CreateMutex(None, False, "Global\\translator-tray-app")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("既に起動しています(トレイアイコンを確認してください)")
        return
    try:
        App().run()
    finally:
        win32api.CloseHandle(mutex)


if __name__ == "__main__":
    main()
