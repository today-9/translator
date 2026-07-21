"""セットアップ CLI: 辞書・モデル・llama.cpp のダウンロードと変換。

usage: uv run translator-setup [dict|fugumt|llama|plamo|qwen|all|company]

company = PLaMo(法人利用に PFN との契約が必要)を除いた構成。
辞書 + FuguMT + Qwen のみで、全コンポーネントが商用利用可のライセンスになる。
"""
from __future__ import annotations

import io
import re
import sqlite3
import sys
import zipfile

import requests

from .paths import (
    DATA_DIR, DICT_DB, FUGUMT_DIR, LLAMA_CPP_DIR, LLAMA_SERVER, PLAMO_GGUF, QWEN_OV_DIR,
)

EJDICT_SRC_URL = "https://raw.githubusercontent.com/kujirahand/EJDict/master/src/{letter}.txt"
FUGUMT_REPO = "staka/fugumt-en-ja"
PLAMO_GGUF_REPO = "mmnga/plamo-2-translate-gguf"
PLAMO_QUANT = "Q4_K_S"
QWEN_REPO = "Qwen/Qwen3-4B-Instruct-2507"
LLAMA_RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"


def setup_dict(force: bool = False) -> None:
    if DICT_DB.exists():
        if not force:
            print(f"[dict] 既に存在: {DICT_DB} (最新版に更新するには --force)")
            _ensure_user_dict()
            return
        try:
            DICT_DB.unlink()
        except PermissionError:
            sys.exit("[dict] 常駐アプリが辞書を使用中です。"
                     "トレイの「終了」で止めてから --force を実行してください")
        print("[dict] 再構築します")
    print("[dict] EJDict-hand をダウンロード中 (a-z の26ファイル)...")
    lines: list[str] = []
    for letter in "abcdefghijklmnopqrstuvwxyz":
        r = requests.get(EJDICT_SRC_URL.format(letter=letter), timeout=60)
        r.raise_for_status()
        r.encoding = "utf-8"
        lines.extend(r.text.splitlines())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DICT_DB)
    conn.execute("CREATE TABLE entries (word TEXT PRIMARY KEY, meaning TEXT NOT NULL)")
    n = 0
    for line in lines:
        if "\t" not in line:
            continue
        head, meaning = line.split("\t", 1)
        # 見出しは "color,colour" のように複数形もある
        for w in head.split(","):
            w = w.strip().lower()
            if not w:
                continue
            conn.execute(
                "INSERT INTO entries VALUES (?, ?) "
                "ON CONFLICT(word) DO UPDATE SET meaning = meaning || ' / ' || excluded.meaning",
                (w, meaning.strip()),
            )
            n += 1
    conn.commit()
    conn.close()
    print(f"[dict] 完了: {n} 見出しを {DICT_DB} に構築")
    _ensure_user_dict()


def _ensure_user_dict() -> None:
    from .engines.dictionary import USER_DICT_TEMPLATE
    from .paths import USER_DICT

    if not USER_DICT.exists():
        USER_DICT.write_text(USER_DICT_TEMPLATE, encoding="utf-8")
        print(f"[dict] ユーザー辞書の雛形を作成: {USER_DICT}")


def setup_fugumt() -> None:
    if (FUGUMT_DIR / "model.bin").exists():
        print(f"[fugumt] 既に存在: {FUGUMT_DIR}")
        return
    print("[fugumt] モデルをダウンロードして CTranslate2 (int8) に変換中...")
    try:
        import transformers  # noqa: F401
    except ImportError:
        sys.exit("[fugumt] convert extra が必要です: uv sync --all-extras")
    import ctranslate2.converters
    from huggingface_hub import hf_hub_download

    FUGUMT_DIR.parent.mkdir(parents=True, exist_ok=True)
    ctranslate2.converters.TransformersConverter(FUGUMT_REPO).convert(
        str(FUGUMT_DIR), quantization="int8", force=True
    )
    # トークナイザ(SentencePiece)はコンバータが持ってこないので別途取得
    for fname in ("source.spm", "target.spm"):
        path = hf_hub_download(FUGUMT_REPO, fname)
        (FUGUMT_DIR / fname).write_bytes(open(path, "rb").read())
    print(f"[fugumt] 完了: {FUGUMT_DIR}")


def setup_llama() -> None:
    if LLAMA_SERVER.exists():
        print(f"[llama] 既に存在: {LLAMA_SERVER}")
        return
    print("[llama] llama.cpp (Windows Vulkan) の最新リリースを取得中...")
    r = requests.get(LLAMA_RELEASE_API, timeout=30)
    r.raise_for_status()
    assets = r.json()["assets"]
    pattern = re.compile(r"win-vulkan.*x64.*\.zip$|bin-win-vulkan-x64\.zip$")
    url = None
    for a in assets:
        if pattern.search(a["name"]):
            url = a["browser_download_url"]
            print(f"[llama] {a['name']} ({a['size'] / 1e6:.0f} MB)")
            break
    if url is None:
        names = ", ".join(a["name"] for a in assets)
        sys.exit(f"[llama] Vulkan版アセットが見つかりません。候補: {names}")
    data = requests.get(url, timeout=600).content
    LLAMA_CPP_DIR.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(LLAMA_CPP_DIR)
    # zip 直下か bin/ 配下かはリリースにより異なるので探して揃える
    if not LLAMA_SERVER.exists():
        found = list(LLAMA_CPP_DIR.rglob("llama-server.exe"))
        if not found:
            sys.exit("[llama] llama-server.exe が見つかりません")
        src_dir = found[0].parent
        for f in src_dir.iterdir():
            f.rename(LLAMA_CPP_DIR / f.name)
    print(f"[llama] 完了: {LLAMA_SERVER}")


def setup_plamo() -> None:
    setup_llama()
    if PLAMO_GGUF.exists():
        print(f"[plamo] 既に存在: {PLAMO_GGUF}")
        return
    from pathlib import Path

    from huggingface_hub import HfApi, hf_hub_download

    files = HfApi().list_repo_files(PLAMO_GGUF_REPO)
    ggufs = sorted(f for f in files if PLAMO_QUANT in f and f.endswith(".gguf"))
    if not ggufs:
        sys.exit(f"[plamo] {PLAMO_QUANT} の gguf が見つかりません: {files}")
    PLAMO_GGUF.parent.mkdir(parents=True, exist_ok=True)
    # 分割 gguf (-00001-of-0000N) の場合はすべて落とし、先頭を所定名にリネームする
    first: Path | None = None
    for fname in ggufs:
        print(f"[plamo] {fname} をダウンロード中 (数GB、時間がかかります)...")
        path = Path(hf_hub_download(
            PLAMO_GGUF_REPO, fname, local_dir=str(PLAMO_GGUF.parent)
        ))
        if first is None:
            first = path
    if len(ggufs) == 1 and first != PLAMO_GGUF:
        first.rename(PLAMO_GGUF)
    elif len(ggufs) > 1:
        # 分割時は llama.cpp が続きを同名パターンで探すためリネームできない
        print(f"[plamo] 分割ggufです。paths.py の PLAMO_GGUF を {first.name} に変更してください")
    print(f"[plamo] 完了: {PLAMO_GGUF if len(ggufs) == 1 else first}")


def setup_qwen() -> None:
    if (QWEN_OV_DIR / "openvino_model.xml").exists() and (QWEN_OV_DIR / "openvino_model.bin").exists():
        print(f"[qwen] 既に存在: {QWEN_OV_DIR}")
        return
    # 公式の変換済みが無いため、元モデル(約8GB)を落として自前で int4 対称量子化する。
    # NPU は対称量子化のみ対応(group_size=128 は 4B 級で推奨の設定)
    print(f"[qwen] {QWEN_REPO} をダウンロードして OpenVINO int4 (sym) に変換中...")
    print("[qwen] 元モデル約8GBのダウンロード+変換で30分以上かかることがあります")
    import subprocess

    cmd = [
        "optimum-cli", "export", "openvino",
        "-m", QWEN_REPO,
        "--task", "text-generation-with-past",
        "--weight-format", "int4",
        "--sym",
        "--group-size", "128",
        "--ratio", "1.0",
        str(QWEN_OV_DIR),
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("[qwen] 変換失敗。convert extra を確認: uv sync --all-extras")
    print(f"[qwen] 完了: {QWEN_OV_DIR}")


TARGETS = {
    "dict": setup_dict,
    "fugumt": setup_fugumt,
    "llama": setup_llama,
    "plamo": setup_plamo,
    "qwen": setup_qwen,
}


def _apply_company_config() -> None:
    """会社PC向けに hook_mode を none にした config を用意する。
    既存 config は上書きしない(既にある場合は注意喚起のみ)。"""
    from .config import DEFAULT_CONFIG
    from .paths import CONFIG_PATH

    if CONFIG_PATH.exists():
        text = CONFIG_PATH.read_text(encoding="utf-8")
        if 'mode = "none"' not in text:
            print('[company] 注意: 既存の config.toml があります。'
                  '[hotkey] の mode を "none" に変更してください'
                  '(フックなし=EDRに検知されないモード)')
        return
    CONFIG_PATH.write_text(
        DEFAULT_CONFIG.replace('mode = "global"', 'mode = "none"'),
        encoding="utf-8",
    )
    print('[company] config.toml を hook_mode="none"(フックなし)で生成しました')


def main() -> None:
    args = sys.argv[1:] or ["all"]
    force = "--force" in args
    args = [a for a in args if a != "--force"] or ["all"]
    company = False
    if args == ["all"]:
        targets = list(TARGETS)
    elif args == ["company"]:
        targets = ["dict", "fugumt", "qwen"]  # PLaMo抜き(全コンポーネント商用可)
        company = True
    else:
        targets = args
    if company:
        _apply_company_config()
    for t in targets:
        if t not in TARGETS:
            sys.exit(f"不明なターゲット: {t} (候補: {', '.join(TARGETS)}, all, company)")
        TARGETS[t](force) if t == "dict" else TARGETS[t]()


if __name__ == "__main__":
    main()
