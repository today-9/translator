"""常駐アプリ本体: トレイ + グローバルホットキー + ポップアップ。"""
from __future__ import annotations

import threading
import tkinter as tk

import keyboard
import pystray
from PIL import Image, ImageDraw, ImageFont

from .clipboard import grab_selection, read_copied_text
from .config import Config, load_config
from .engines import SENTENCE_ENGINES, get_engine
from .engines.base import EngineNotReady
from .popup import PopupManager
from .service import translate


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
        self.tray: pystray.Icon | None = None

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

        now = _time.monotonic()
        is_double = (now - self._last_ctrl_c) * 1000 <= self.cfg.double_press_ms
        self._last_ctrl_c = now
        if is_double:
            self._last_ctrl_c = 0.0  # 3連打で2回発火しないようリセット
            self.on_hotkey()

    def _capture_and_translate(self) -> None:
        try:
            if self.cfg.hotkey == "double-ctrl-c":
                text = read_copied_text()  # ユーザーが自分でコピー済み
            else:
                text = grab_selection(self.cfg.hotkey)
            if not text:
                self.popup.show("(選択テキストを取得できませんでした)", header="translator")
                return
            preview = text if len(text) <= 60 else text[:57] + "..."
            engine = self.cfg.sentence_engine
            slow = engine in ("plamo", "qwen_npu")
            if slow:
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
        hotkey_label = ("Ctrl+C ×2" if self.cfg.hotkey == "double-ctrl-c"
                        else self.cfg.hotkey)
        return pystray.Menu(
            pystray.MenuItem(f"ホットキー: {hotkey_label}", None, enabled=False),
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
        keyboard.unhook_all()
        self.root.after(0, self.root.destroy)

    # ---- 起動 ----
    def run(self) -> None:
        if self.cfg.hotkey == "double-ctrl-c":
            keyboard.add_hotkey("ctrl+c", self.on_ctrl_c, suppress=False)
        else:
            keyboard.add_hotkey(self.cfg.hotkey, self.on_hotkey, suppress=False)

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

        hint = ("テキストを選択して Ctrl+C を2連打で翻訳します"
                if self.cfg.hotkey == "double-ctrl-c"
                else f"テキストを選択して {self.cfg.hotkey} で翻訳します")
        self.popup.show(f"起動しました。{hint}", header="translator")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._quit()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
