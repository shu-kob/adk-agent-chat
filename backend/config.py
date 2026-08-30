"""
環境変数およびグローバル設定管理モジュール (backend/config.py)

【役割】
- .env ファイルから各種設定値をロードし、バックエンド全体（main.py, agent.py, runner.py 等）に提供する。
- Google AI Studio (API Key方式) と Google Cloud Vertex AI (ADC認証方式) の切り替え制御を行う。
"""

import os
from dotenv import load_dotenv

# .env ファイルから環境変数をロード
load_dotenv()

# ==============================================================================
# Google GenAI / Vertex AI 認証設定
# ==============================================================================
# Google AI Studio 用の API キー (AI Studio 経由時に使用)
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "").strip().strip('"\'')

# Vertex AI をバックエンドとして使用するかどうかのフラグ ('true', '1', 'yes' で有効化)
USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1", "yes")

# Vertex AI 使用時の Google Cloud プロジェクト ID
GCP_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip().strip('"\'')

# Vertex AI 使用時のリージョン (例: 'global', 'us-central1', 'asia-northeast1')
GCP_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip().strip('"\'')

# ==============================================================================
# チャットボット モデル & サーバー設定
# ==============================================================================
# チャットで使用するデフォルトの Gemini モデル名 (Vertex AI の場合は 2.5-flash、AI Studio の場合は 3.5-flash-lite を既定とする)
GEMINI_MODEL: str = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash" if USE_VERTEXAI else "gemini-3.5-flash-lite"
)

# FastAPI サーバーのバインドホストアドレス (デフォルト: 0.0.0.0)
HOST: str = os.getenv("HOST", "0.0.0.0")

# FastAPI サーバーのバインドポート番号 (デフォルト: 8000)
PORT: int = int(os.getenv("PORT", "8000"))
