"""ワンショット翻訳 CLI(動作確認用)。

usage: uv run translator-cli [--engine fugumt|plamo|qwen_npu|dictionary] "text"
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config
from .service import translate


def main() -> None:
    parser = argparse.ArgumentParser(description="EN->JA offline translator CLI")
    parser.add_argument("text", nargs="+", help="翻訳する英文")
    parser.add_argument("--engine", "-e", default=None,
                        choices=["dictionary", "fugumt", "plamo", "qwen_npu"],
                        help="エンジン指定(省略時は自動判定)")
    args = parser.parse_args()

    cfg = load_config()
    text = " ".join(args.text)
    try:
        result = translate(text, cfg, engine_name=args.engine)
    except Exception as e:
        sys.exit(f"エラー: {e}")
    print(result.text)
    print(f"--- {result.engine_label} / {result.elapsed:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
