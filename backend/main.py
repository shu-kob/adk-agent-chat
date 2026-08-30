"""
FastAPI バックエンド API エントリーポイント (backend/main.py)

【役割】
- React フロントエンドからの REST API リクエストを受け付け、ルーティング・バリデーションを行う。
- Google ADK Agent (`agent_manager`) と連携してチャット応答を生成・返却する。
- セッションの初期化、破棄、ヘルスチェック、設定確認エンドポイントを提供する。
"""

import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 外部設定・エージェントマネージャーの参照
import config  # config.py から GEMINI_MODEL, GOOGLE_API_KEY, HOST, PORT を参照
from agent import agent_manager  # agent.py から ChatAgentManager シングルトンを参照

# ==============================================================================
# FastAPI アプリケーション初期化
# ==============================================================================
app = FastAPI(
    title="ADK Agent Chat API",
    description="Google Agent Development Kit (ADK) および Gemini を利用したチャットボット用 FastAPI バックエンド",
    version="1.0.0"
)

# React フロントエンド (localhost:3000 等) からのアクセスを許可する CORS ミドルウェア設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# リクエスト / レスポンス データモデル定義 (Pydantic)
# ==============================================================================
class ChatRequest(BaseModel):
    """
    チャット送信リクエストモデル
    - message: ユーザーからの入力テキスト (必須)
    - session_id: 会話履歴を保持・識別するセッションID (省略時は新規UUID発行)
    - user_id: ユーザー識別子 (デフォルト: 'default_user')
    """
    message: str = Field(..., description="ユーザーからの入力プロンプト/メッセージ", json_schema_extra={"example": "こんにちは！何ができますか？"})
    session_id: Optional[str] = Field(default=None, description="会話メモリ用のユニークなセッションID")
    user_id: Optional[str] = Field(default="default_user", description="ユーザー識別子")

class ChatResponse(BaseModel):
    """
    チャット応答レスポンスモデル
    - reply: AI アシスタントからの返答テキスト
    - session_id: 使用されたセッションID
    - model: 応答生成に使用されたモデル名
    """
    reply: str
    session_id: str
    model: str

class ResetSessionRequest(BaseModel):
    """
    セッションリセット要求モデル
    - session_id: 破棄対象のセッションID
    - user_id: ユーザー識別子
    """
    session_id: str
    user_id: Optional[str] = Field(default="default_user")

class ResetSessionResponse(BaseModel):
    """
    セッションリセット応答モデル
    """
    status: str
    session_id: str

# ==============================================================================
# API エンドポイント定義
# ==============================================================================
@app.get("/api/health")
async def health_check():
    """
    システムの稼働状態および現在設定されているモデル情報を返却するヘルスチェックエンドポイント
    """
    return {
        "status": "ok",
        "model": config.GEMINI_MODEL,
        "adk_agent": "initialized"
    }

@app.get("/api/config")
async def get_config():
    """
    フロントエンド向けの設定情報（モデル名、APIキー設定有無）を返却するエンドポイント
    """
    has_api_key = bool(config.GOOGLE_API_KEY) or config.USE_VERTEXAI
    return {
        "model": config.GEMINI_MODEL,
        "has_api_key": has_api_key
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    ユーザーからのメッセージを受け取り、Google ADK Agent 経由で応答を生成して返却するメインエンドポイント
    
    【処理の流れ】
    1. メッセージが空でないかバリデーション (空なら HTTP 400 を送出)
    2. session_id が指定されていない場合は新規 UUID を生成
    3. agent_manager.generate_response を呼び出して AI 応答を取得
    4. ChatResponse 形式で返却
    """
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty."
        )

    session_id = request.session_id or str(uuid.uuid4())
    user_id = request.user_id or "default_user"

    reply = await agent_manager.generate_response(
        session_id=session_id,
        prompt=request.message.strip(),
        user_id=user_id
    )

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        model=config.GEMINI_MODEL
    )

@app.post("/api/sessions/reset", response_model=ResetSessionResponse)
async def reset_session_endpoint(request: ResetSessionRequest):
    """
    指定されたセッションIDのメモリ（会話履歴）を破棄しリセットするエンドポイント
    """
    await agent_manager.clear_session(session_id=request.session_id, user_id=request.user_id or "default_user")
    return ResetSessionResponse(
        status="session_cleared",
        session_id=request.session_id
    )

# 開発サーバー直接起動用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
