"""プロジェクト内のデータ配置。モデル・辞書はすべて data/ 以下に置く。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_PATH = PROJECT_ROOT / "config.toml"

DICT_DB = DATA_DIR / "ejdict.sqlite3"
FUGUMT_DIR = DATA_DIR / "models" / "fugumt-en-ja-ct2"
PLAMO_GGUF = DATA_DIR / "models" / "plamo-2-translate-Q4_K_S.gguf"
QWEN_OV_DIR = DATA_DIR / "models" / "qwen3-4b-instruct-2507-int4-ov"
LLAMA_CPP_DIR = DATA_DIR / "llama.cpp"
LLAMA_SERVER = LLAMA_CPP_DIR / "llama-server.exe"
