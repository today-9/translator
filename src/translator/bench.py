"""エンジン比較ベンチマーク。

usage: uv run translator-bench [--engines fugumt plamo qwen_npu] [--runs 2]
結果は表示に加えて bench_results.md に保存する。
"""
from __future__ import annotations

import argparse
import time

from .config import load_config
from .engines import SENTENCE_ENGINES, get_engine
from .paths import PROJECT_ROOT

TEST_SENTENCES = [
    # 短文
    "The quick brown fox jumps over the lazy dog.",
    # 技術文
    "The function returns a promise that resolves when all pending writes "
    "have been flushed to disk.",
    # ニュアンスのある文
    "I couldn't help but notice that the deadline has been quietly pushed "
    "back twice already.",
    # 段落
    "Machine translation has improved dramatically over the past decade. "
    "Neural models now capture context across entire sentences, producing "
    "output that often reads naturally. However, they still struggle with "
    "idioms, cultural references, and highly technical jargon.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="翻訳エンジン比較ベンチ")
    parser.add_argument("--engines", nargs="+", default=SENTENCE_ENGINES,
                        choices=SENTENCE_ENGINES)
    parser.add_argument("--runs", type=int, default=2,
                        help="計測回数(初回=ロード込み、2回目以降=定常)")
    args = parser.parse_args()

    cfg = load_config()
    report: list[str] = ["# 翻訳エンジン比較ベンチマーク\n"]
    summary: list[tuple[str, str, float, float]] = []

    for name in args.engines:
        engine = get_engine(name, cfg)
        if not engine.is_ready():
            print(f"=== {name}: 未セットアップのためスキップ "
                  f"(uv run translator-setup {name.split('_')[0]})")
            continue
        print(f"=== {name}: ロード中...")
        t0 = time.perf_counter()
        try:
            engine.warmup()
        except Exception as e:
            print(f"=== {name}: ロード失敗: {e}")
            report.append(f"## {name}\n\nロード失敗: {e}\n")
            continue
        load_time = time.perf_counter() - t0
        print(f"=== {name} ({engine.label}) ロード {load_time:.1f}s")
        report.append(f"## {engine.label}\n\n- モデルロード: {load_time:.1f}s\n")

        for i, sent in enumerate(TEST_SENTENCES, 1):
            times = []
            output = ""
            for _ in range(max(args.runs, 1)):
                t0 = time.perf_counter()
                output = engine.translate(sent)
                times.append(time.perf_counter() - t0)
            best = min(times)
            print(f"  [{i}] {best:.2f}s  {output[:60]}")
            report.append(
                f"### 文{i} ({best:.2f}s)\n\n> {sent}\n\n{output}\n"
            )
            summary.append((name, f"文{i}", times[0], best))

    # サマリー表
    report.append("\n## レイテンシ一覧 (秒)\n")
    report.append("| エンジン | 文 | 初回 | ベスト |")
    report.append("|---|---|---|---|")
    for name, sent, first, best in summary:
        report.append(f"| {name} | {sent} | {first:.2f} | {best:.2f} |")

    out = PROJECT_ROOT / "bench_results.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"\n結果を {out} に保存しました")


if __name__ == "__main__":
    main()
