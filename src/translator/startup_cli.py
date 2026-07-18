"""Windowsスタートアップ登録 CLI。

usage: uv run translator-startup [install|uninstall|status|run]

install   ログイン時に pythonw.exe(コンソールなし)で自動起動するショートカットを登録
uninstall 登録を解除
status    登録状態を表示
run       登録はせず、今すぐコンソールなしで常駐を起動(ターミナルは閉じてよい)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .paths import PROJECT_ROOT

SHORTCUT = (Path(os.environ["APPDATA"]) /
            "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" /
            "translator.lnk")
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
VBS = PROJECT_ROOT / "data" / "translator-hidden.vbs"
WSCRIPT = Path(os.environ["SystemRoot"]) / "System32" / "wscript.exe"

# 注意: pythonw.exe は使わない。uv 配布の python は未署名で、Smart App Control
# 等のアプリ制御が(実行実績の少ない)pythonw.exe を評判ベースでブロックする
# ことがある。python.exe をウィンドウ非表示で起動する方式なら通る。


def _write_vbs() -> None:
    VBS.parent.mkdir(parents=True, exist_ok=True)
    VBS.write_text(
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{PROJECT_ROOT}"\n'
        f'sh.Run """{PYTHON}"" -m translator.app", 0, False\n',
        encoding="utf-8",
    )


def install() -> None:
    if not PYTHON.exists():
        sys.exit(f"python.exe が見つかりません: {PYTHON}\n先に `uv sync` を実行してください")
    import win32com.client

    _write_vbs()
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(SHORTCUT))
    sc.TargetPath = str(WSCRIPT)  # 署名済みのMS製バイナリ経由で非表示起動
    sc.Arguments = f'"{VBS}"'
    sc.WorkingDirectory = str(PROJECT_ROOT)
    sc.Description = "オフライン英日翻訳 常駐ツール"
    sc.Save()
    print(f"登録しました: {SHORTCUT}")
    print("次回ログインから自動起動します。今すぐ起動: uv run translator-startup run")


def uninstall() -> None:
    if SHORTCUT.exists():
        SHORTCUT.unlink()
        print(f"解除しました: {SHORTCUT}")
    else:
        print("登録されていません")


def status() -> None:
    print(f"登録{'済み' if SHORTCUT.exists() else 'なし'}: {SHORTCUT}")


def run() -> None:
    if not PYTHON.exists():
        sys.exit(f"python.exe が見つかりません: {PYTHON}\n先に `uv sync` を実行してください")
    import subprocess

    # CREATE_NO_WINDOW: 子は自分専用の不可視コンソールを持つため、
    # このターミナルを閉じてもアプリは終了しない
    subprocess.Popen(
        [str(PYTHON), "-m", "translator.app"],
        cwd=str(PROJECT_ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    print("常駐を起動しました(コンソールなし)。このターミナルは閉じて構いません")
    print("終了はトレイアイコン右クリック → 終了")


def main() -> None:
    actions = {"install": install, "uninstall": uninstall, "status": status, "run": run}
    arg = sys.argv[1] if len(sys.argv) > 1 else "install"
    if arg not in actions:
        sys.exit(f"usage: translator-startup [{'|'.join(actions)}]")
    actions[arg]()


if __name__ == "__main__":
    main()
