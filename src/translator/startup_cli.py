"""Windowsスタートアップ登録 CLI。

usage: uv run translator-startup [install|uninstall|status]

ログイン時に pythonw.exe(コンソールなし)で常駐アプリを自動起動する
ショートカットを shell:startup に作成・削除する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .paths import PROJECT_ROOT

SHORTCUT = (Path(os.environ["APPDATA"]) /
            "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" /
            "translator.lnk")
PYTHONW = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"


def install() -> None:
    if not PYTHONW.exists():
        sys.exit(f"pythonw.exe が見つかりません: {PYTHONW}\n先に `uv sync` を実行してください")
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(SHORTCUT))
    sc.TargetPath = str(PYTHONW)
    sc.Arguments = "-m translator.app"
    sc.WorkingDirectory = str(PROJECT_ROOT)
    sc.Description = "オフライン英日翻訳 常駐ツール"
    sc.Save()
    print(f"登録しました: {SHORTCUT}")
    print("次回ログインから自動起動します。今すぐ起動する場合:")
    print(f'  Start-Process "{PYTHONW}" -ArgumentList "-m","translator.app"')


def uninstall() -> None:
    if SHORTCUT.exists():
        SHORTCUT.unlink()
        print(f"解除しました: {SHORTCUT}")
    else:
        print("登録されていません")


def status() -> None:
    print(f"登録{'済み' if SHORTCUT.exists() else 'なし'}: {SHORTCUT}")


def main() -> None:
    actions = {"install": install, "uninstall": uninstall, "status": status}
    arg = sys.argv[1] if len(sys.argv) > 1 else "install"
    if arg not in actions:
        sys.exit(f"usage: translator-startup [{'|'.join(actions)}]")
    actions[arg]()


if __name__ == "__main__":
    main()
