"""
Google Agent Development Kit (ADK) エージェント & セッションライフサイクル管理モジュール (backend/agent.py)

【役割】
- Google ADK の LlmAgent, Runner, InMemorySessionService をインスタンス化し、会話コンテキストをセッションID単位で管理する。
- 評価モード（allow_fallback=False）および本番チャットモード（allow_fallback=True: ADK失敗時にgoogle-genai直呼びへフォールバック）を制御する。
- 実行経路（'adk' または 'genai_sdk_fallback'）を追跡・記録する。
"""

import asyncio
import logging
from typing import Optional, List, Dict
import os
import config  # config.py から GEMINI_MODEL, GOOGLE_API_KEY, USE_VERTEXAI, GCP_PROJECT 等を参照

logger = logging.getLogger("adk_agent")

# Google ADK パッケージのインポート試行
try:
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    logger.warning("google-adk パッケージが見つかりません。google-genai SDK 直接呼び出しへフォールバックします。")

# Google GenAI SDK パッケージのインポート試行
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-genai パッケージが見つかりません。")


class ChatAgentManager:
    """
    Google ADK Agent のインスタンス、ランナー、およびセッションのライフサイクルを統合管理するクラス
    """
    def __init__(self, model_name: str = config.GEMINI_MODEL, allow_fallback: bool = True):
        """
        初期化メソッド
        
        :param model_name: 使用する Gemini モデル名 (デフォルト: config.GEMINI_MODEL)
        :param allow_fallback: ADK 実行失敗時に GenAI SDK 直呼びへフォールバックすることを許可するかどうか。
                              評価実行時は測定の厳密性を確保するため False を指定する。
        """
        self.model_name = model_name
        self.allow_fallback = allow_fallback
        self.last_execution_path: Optional[str] = None  # 直近の実行経路 ('adk' または 'genai_sdk_fallback')
        self.history: Dict[str, List[Dict[str, str]]] = {}  # セッションごとの会話コンテキスト履歴
        self.session_service = None
        self.runner = None
        self.adk_agent = None
        self._init_adk()

    def _init_adk(self):
        """
        Google ADK の LlmAgent, InMemorySessionService, Runner を初期化する内部メソッド
        """
        if ADK_AVAILABLE:
            try:
                # 1. システムインストラクションを付与した LlmAgent の作成
                self.adk_agent = LlmAgent(
                    name="chat_assistant",
                    model=self.model_name,
                    instruction=(
                        "You are a helpful, friendly, and highly intelligent AI assistant powered by "
                        f"Google ADK and Gemini ({self.model_name}). "
                        "Respond concisely and accurately in markdown format when appropriate."
                    )
                )
                # 2. セッション管理サービスの作成
                self.session_service = InMemorySessionService()
                # 3. エージェントを実行する Runner の作成
                self.runner = Runner(
                    agent=self.adk_agent,
                    app_name="adk_chat_app",
                    session_service=self.session_service
                )
                logger.info(f"ADK Agent の初期化に成功しました (モデル: {self.model_name})")
            except Exception as e:
                logger.error(f"ADK Agent の初期化に失敗しました: {e}")

    async def get_or_create_session(self, session_id: str, user_id: str = "default_user"):
        """
        指定されたセッションIDに対応するセッションオブジェクトを取得、存在しなければ新規作成する。
        
        :param session_id: セッションの一意識別子
        :param user_id: ユーザー識別子
        :return: Session オブジェクト (取得不可の場合は None)
        """
        if ADK_AVAILABLE and self.session_service:
            try:
                res = self.session_service.get_session(
                    app_name="adk_chat_app",
                    user_id=user_id,
                    session_id=session_id
                )
                session = await res if asyncio.iscoroutine(res) else res

                if not session:
                    res_create = self.session_service.create_session(
                        app_name="adk_chat_app",
                        user_id=user_id,
                        session_id=session_id
                    )
                    session = await res_create if asyncio.iscoroutine(res_create) else res_create
                return session
            except Exception as e:
                logger.error(f"セッション {session_id} の取得/作成中にエラーが発生しました: {e}")
        return None

    async def generate_response(self, session_id: str, prompt: str, user_id: str = "default_user") -> str:
        """
        ユーザープロンプトを処理し、AI からのテキスト応答を生成して返却する。
        
        :param session_id: 会話履歴を保持するセッションID
        :param prompt: ユーザー入力テキスト
        :param user_id: ユーザー識別子
        :return: 生成された応答文字列
        :raises RuntimeError: allow_fallback=False かつ ADK 実行失敗時に例外を送出
        """
        self.last_execution_path = None

        # 認証情報の事前検証
        if not config.USE_VERTEXAI and not config.GOOGLE_API_KEY:
            return (
                "⚠️ Authentication missing. Please set `GOOGLE_API_KEY` for AI Studio, "
                "or set `GOOGLE_GENAI_USE_VERTEXAI=true` and run `gcloud auth application-default login`."
            )

        # 1. Google ADK Runner 経由でのエージェント非同期実行を優先試行 (run_async)
        if ADK_AVAILABLE and self.runner:
            try:
                await self.get_or_create_session(session_id=session_id, user_id=user_id)
                response_text = ""
                
                # ADK Runner の非同期ジェネレータメソッド run_async を呼び出し
                if hasattr(self.runner, "run_async"):
                    events = self.runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=prompt
                    )
                else:
                    # 後方互換性フォールバック
                    events = self.runner.run(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=prompt
                    )

                events = await events if asyncio.iscoroutine(events) else events

                if isinstance(events, str):
                    self.last_execution_path = "adk"
                    return events

                # 非同期イテレータ (AsyncGenerator) からテキストを抽出
                if hasattr(events, "__aiter__"):
                    async for event in events:
                        if hasattr(event, "content") and event.content:
                            response_text += str(event.content)
                        elif hasattr(event, "text"):
                            response_text += str(event.text)
                elif hasattr(events, "__iter__"):
                    for event in events:
                        if hasattr(event, "content") and event.content:
                            response_text += str(event.content)
                        elif hasattr(event, "text"):
                            response_text += str(event.text)

                if response_text:
                    self.last_execution_path = "adk"
                    return response_text
            except Exception as e:
                if not self.allow_fallback:
                    logger.error(f"ADK runner error (フォールバック無効モード): {e}")
                    raise
                logger.warning(f"ADK runner 実行エラー: {e}。GenAI SDK 直接呼び出しへフォールバックします。")

        # フォールバック無効モードで ADK が失敗した場合は例外を送出
        if ADK_AVAILABLE and not self.allow_fallback:
            raise RuntimeError("ADK runner could not process request and fallback is disabled.")

        # 2. google-genai SDK 直接呼び出しへのフォールバック (チャット本番用: asyncio.to_thread でノンブロッキング化)
        if GENAI_AVAILABLE:
            try:
                if config.USE_VERTEXAI:
                    client = genai.Client(
                        vertexai=True,
                        project=config.GCP_PROJECT,
                        location=config.GCP_LOCATION
                    )
                else:
                    client = genai.Client(api_key=config.GOOGLE_API_KEY)

                # 同期 API 呼び出しをスレッドプールへ委譲し、FastAPI イベントループのブロックを防止
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.model_name,
                    contents=prompt
                )
                self.last_execution_path = "genai_sdk_fallback"
                return response.text if response.text else "No response generated."
            except Exception as e:
                logger.error(f"GenAI SDK 実行エラー: {e}")
                if not self.allow_fallback:
                    raise
                return f"Error communicating with Gemini ({self.model_name}): {str(e)}"

        if not self.allow_fallback:
            raise RuntimeError("Neither google-adk nor google-genai could process the request.")

        return "Error: Neither google-adk nor google-genai could process the request."

    def get_conversation_context(self, session_id: str) -> List[Dict[str, str]]:
        """
        指定されたセッションIDの直前までの会話コンテキスト履歴を取得する。
        
        :param session_id: セッションID
        :return: [{"role": "user"|"assistant", "text": "..."}] のリスト
        """
        return list(self.history.get(session_id, []))

    def append_conversation_turn(self, session_id: str, role: str, text: str):
        """
        セッション履歴に会話ターンを追加する。
        
        :param session_id: セッションID
        :param role: 'user' または 'assistant'
        :param text: 発言内容
        """
        self.history.setdefault(session_id, []).append({"role": role, "text": text})

    async def clear_session(self, session_id: str, user_id: str = "default_user") -> bool:
        """
        指定されたセッションIDの会話履歴メモリを破棄する。
        
        :param session_id: 破棄対象のセッションID
        :param user_id: ユーザー識別子
        :return: 破棄成功フラグ (bool)
        """
        self.history.pop(session_id, None)
        if ADK_AVAILABLE and self.session_service:
            try:
                res = self.session_service.delete_session(
                    app_name="adk_chat_app",
                    user_id=user_id,
                    session_id=session_id
                )
                if asyncio.iscoroutine(res):
                    await res
                return True
            except Exception as e:
                logger.error(f"セッション {session_id} の削除中にエラーが発生しました: {e}")
        return True

# シングルトンインスタンスの生成 (FastAPI 等から共有参照)
agent_manager = ChatAgentManager()
