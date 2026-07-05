"""PLaMo翻訳 (pfnet/plamo-2-translate) を llama.cpp サーバー(Vulkan/iGPU)で実行。

llama-server を子プロセスとして起動し、HTTP /completion を叩く。
サーバーは初回翻訳時に起動(preload=true なら warmup 時)。
"""
from __future__ import annotations

import atexit
import subprocess
import threading
import time

import requests

from ..config import Config
from ..paths import LLAMA_SERVER, PLAMO_GGUF
from .base import Engine, EngineNotReady

PROMPT_TEMPLATE = (
    "<|plamo:op|>dataset\n"
    "translation\n\n"
    "<|plamo:op|>input lang=English\n"
    "{text}\n"
    "<|plamo:op|>output lang=Japanese\n"
)


class PlamoEngine(Engine):
    name = "plamo"
    label = "PLaMo翻訳 (CPU)"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    @property
    def _base_url(self) -> str:
        return f"http://127.0.0.1:{self._cfg.plamo_port}"

    def is_ready(self) -> bool:
        return PLAMO_GGUF.exists() and LLAMA_SERVER.exists()

    def _server_alive(self) -> bool:
        try:
            r = requests.get(f"{self._base_url}/health", timeout=1)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def _ensure_server(self) -> None:
        if self._server_alive():
            return
        if not self.is_ready():
            raise EngineNotReady("PLaMo未配置。`uv run translator-setup plamo` を実行してください")
        if self._proc is None or self._proc.poll() is not None:
            args = [
                str(LLAMA_SERVER),
                "-m", str(PLAMO_GGUF),
                "--port", str(self._cfg.plamo_port),
                "--host", "127.0.0.1",
                "-ngl", str(self._cfg.plamo_n_gpu_layers),
                "--ctx-size", str(self._cfg.plamo_ctx_size),
                "--threads", "6",
            ]
            if self._cfg.plamo_n_gpu_layers == 0:
                # Vulkan ビルドは ngl=0 でも長いプロンプトの行列演算を GPU に
                # オフロードし、plamo2 では出力が崩壊する。デバイスごと切るのが正解
                args += ["--device", "none"]
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            atexit.register(self.shutdown)  # CLI/ベンチ終了時に孤児化させない
        # 5.5GB のモデルロード待ち
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self._server_alive():
                return
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"llama-server が終了しました (exit={self._proc.returncode})。"
                    "Vulkan非対応の場合は config.toml で n_gpu_layers = 0 を試してください"
                )
            time.sleep(1)
        raise RuntimeError("llama-server の起動がタイムアウトしました")

    def warmup(self) -> None:
        with self._lock:
            self._ensure_server()

    def translate(self, text: str) -> str:
        with self._lock:
            self._ensure_server()
            # 通常は EOS で止まるが、暴走時の保険として入力長に応じた上限を掛ける
            n_predict = min(1024, len(text.split()) * 4 + 48)
            r = requests.post(
                f"{self._base_url}/completion",
                json={
                    "prompt": PROMPT_TEMPLATE.format(text=text),
                    "n_predict": n_predict,
                    "temperature": 0.0,
                    "stop": ["<|plamo:op|>"],
                },
                timeout=300,
            )
            r.raise_for_status()
            return r.json()["content"].strip()

    def shutdown(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            self._proc = None
