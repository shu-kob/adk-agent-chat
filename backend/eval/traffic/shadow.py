"""
オンライン・シャドウテスト実行モジュール (backend/eval/traffic/shadow.py)

【役割】
- 書籍『Building Reliable AI Systems』Chapter 10.5「Shadow-testing new models」に基づく実装。
- 本番対話 API (/api/chat) へのライブリクエストに対して、ユーザー応答の遅延や体験に影響を与えることなく
  非同期 (asyncio.create_task) で候補モデル (Candidate Model) に同一入力を投げて並行評価する。
- サンプリング率 (SHADOW_SAMPLE_RATE) により評価コストを制御可能。
- 個人情報 (PII) マスキングを適用した上で、本番結果と候補結果のペアログを JSON Lines 形式で永続化する。
- 候補モデルのエラー発生時も例外を内部吸収し、本番サービスへの影響をゼロにする。
"""

import os
import json
import time
import uuid
import random
import logging
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import config
from eval.traffic.store import default_pii_masking_hook
from eval.runner import MODEL_PRICING, calculate_cost

# Google GenAI クライアントのインポート試行
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

logger = logging.getLogger("eval.traffic.shadow")

# 既定のシャドウテストログ保存先
DEFAULT_SHADOW_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "data", "shadow_log.jsonl"
)


class ShadowRunner:
    """
    本番トラフィックに対するオンライン・シャドウテスト実行管理クラス
    """
    def __init__(
        self,
        enabled: Optional[bool] = None,
        candidate_model_id: Optional[str] = None,
        sample_rate: Optional[float] = None,
        timeout_sec: Optional[float] = None,
        log_file_path: Optional[str] = None,
        masking_hook: Optional[Callable[[str], str]] = default_pii_masking_hook,
        client: Optional[Any] = None
    ):
        """
        初期化メソッド

        :param enabled: シャドウテストの有効化フラグ (省略時は config.SHADOW_TEST_ENABLED)
        :param candidate_model_id: 候補モデル名 (省略時は config.SHADOW_MODEL_ID)
        :param sample_rate: サンプリング率 (省略時は config.SHADOW_SAMPLE_RATE)
        :param timeout_sec: タイムアウト秒数 (省略時は config.SHADOW_TIMEOUT_SEC)
        :param log_file_path: ログ保存先 JSONL パス (省略時は config.SHADOW_LOG_PATH)
        :param masking_hook: PII マスキング関数 (省略時は default_pii_masking_hook)
        :param client: テスト用のモックまたは google.genai.Client インスタンス
        """
        self.enabled = config.SHADOW_TEST_ENABLED if enabled is None else enabled
        self.candidate_model_id = candidate_model_id or config.SHADOW_MODEL_ID
        self.sample_rate = config.SHADOW_SAMPLE_RATE if sample_rate is None else sample_rate
        self.timeout_sec = config.SHADOW_TIMEOUT_SEC if timeout_sec is None else timeout_sec
        self.log_file_path = log_file_path or config.SHADOW_LOG_PATH or DEFAULT_SHADOW_LOG_PATH
        self.masking_hook = masking_hook
        self.client = client
        self._lock = threading.Lock()

        # 保存先ディレクトリの作成
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    def _get_client(self):
        """GenAI クライアントを遅延初期化して取得する"""
        if self.client is not None:
            return self.client

        if not GENAI_AVAILABLE:
            return None

        if config.USE_VERTEXAI:
            return genai.Client(
                vertexai=True,
                project=config.GCP_PROJECT,
                location=config.GCP_LOCATION
            )
        else:
            return genai.Client(api_key=config.GOOGLE_API_KEY)

    def should_sample(self) -> bool:
        """
        設定フラグおよびサンプリング率に基づいて、現在のリクエストをシャドウテスト対象にするかを判定する。
        """
        if not self.enabled:
            return False
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
        return random.random() < self.sample_rate

    def schedule_shadow(
        self,
        session_id: str,
        input_text: str,
        conversation_context: List[Dict[str, str]],
        production_output: str,
        production_model_id: str,
        production_latency_ms: int,
        instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None
    ) -> Optional[asyncio.Task]:
        """
        本番リクエストの完了時に呼び出され、条件合致時に非同期タスク (asyncio.create_task) で
        シャドウテストをスケジュールする（ノンブロッキング）。

        :return: 生成された asyncio.Task (対象外またはエラー時は None)
        """
        if not self.should_sample():
            return None

        try:
            # 現在のイベントループを取得して非同期タスクを作成
            task = asyncio.create_task(
                self.execute_shadow(
                    session_id=session_id,
                    input_text=input_text,
                    conversation_context=conversation_context,
                    production_output=production_output,
                    production_model_id=production_model_id,
                    production_latency_ms=production_latency_ms,
                    instruction=instruction,
                    generation_config=generation_config
                )
            )
            return task
        except Exception as e:
            logger.warning(f"Failed to schedule shadow test task: {e}")
            return None

    async def execute_shadow(
        self,
        session_id: str,
        input_text: str,
        conversation_context: List[Dict[str, str]],
        production_output: str,
        production_model_id: str,
        production_latency_ms: int,
        instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        候補モデルに対して非同期にプロンプトを送信し、結果を本番出力とペアにして記録する。
        例外が発生した場合でも本番に影響を与えないよう内部でキャッチしてエラーログとして記録する。
        """
        gen_cfg = generation_config or {}
        temperature = gen_cfg.get("temperature", 0.0)
        seed = gen_cfg.get("seed", 42)
        max_output_tokens = gen_cfg.get("max_output_tokens", 4096)
        system_inst = instruction or (
            "You are a helpful, friendly, and highly intelligent AI assistant."
        )

        candidate_output = ""
        prompt_tokens = 0
        candidate_tokens = 0
        finish_reason = None
        cost_usd = 0.0
        status = "success"
        error_message = None

        start_time = time.time()

        try:
            client = self._get_client()
            if client is None:
                # モック環境または SDK 不可時
                candidate_output = f"[MOCK SHADOW] Candidate {self.candidate_model_id} response"
                prompt_tokens = 40
                candidate_tokens = 20
                finish_reason = "STOP"
            else:
                # コンテキストの整形
                full_prompt_parts = []
                if conversation_context:
                    full_prompt_parts.append("【過去の会話履歴】")
                    for msg in conversation_context:
                        role = "ユーザー" if msg.get("role") == "user" else "アシスタント"
                        full_prompt_parts.append(f"{role}: {msg.get('text', '')}")
                    full_prompt_parts.append("\n【現在のユーザー入力】")
                full_prompt_parts.append(input_text)
                merged_prompt = "\n".join(full_prompt_parts)

                config_obj = types.GenerateContentConfig(
                    temperature=temperature,
                    seed=seed,
                    max_output_tokens=max_output_tokens,
                    system_instruction=system_inst
                )

                # asyncio.to_thread で同期 SDK 呼び出しをノンブロッキング実行 (タイムアウト保護付き)
                def _call():
                    return client.models.generate_content(
                        model=self.candidate_model_id,
                        contents=merged_prompt,
                        config=config_obj
                    )

                response = await asyncio.wait_for(
                    asyncio.to_thread(_call),
                    timeout=self.timeout_sec
                )

                candidate_output = response.text if response.text else ""

                if response.candidates and len(response.candidates) > 0:
                    c = response.candidates[0]
                    if hasattr(c, "finish_reason") and c.finish_reason is not None:
                        val = getattr(c.finish_reason, "name", c.finish_reason)
                        finish_reason = str(val) if val is not None else None

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    um = response.usage_metadata
                    prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
                    candidate_tokens = getattr(um, "candidates_token_count", 0) or 0

            cost_usd = calculate_cost(self.candidate_model_id, prompt_tokens, candidate_tokens)

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"Shadow test execution error for model {self.candidate_model_id}: {e}")

        cand_latency_ms = int((time.time() - start_time) * 1000)

        # PII マスキングの適用
        safe_input = self.masking_hook(input_text) if self.masking_hook else input_text
        safe_prod_out = self.masking_hook(production_output) if self.masking_hook else production_output
        safe_cand_out = self.masking_hook(candidate_output) if self.masking_hook else candidate_output

        safe_context = []
        if conversation_context and self.masking_hook:
            for turn in conversation_context:
                safe_context.append({
                    "role": turn.get("role", "unknown"),
                    "text": self.masking_hook(turn.get("text", ""))
                })
        else:
            safe_context = conversation_context or []

        # シャドウレコードの構築
        record = {
            "shadow_id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "input_text": safe_input,
            "conversation_context": safe_context,
            "production": {
                "model_id": production_model_id,
                "output_text": safe_prod_out,
                "latency_ms": production_latency_ms
            },
            "candidate": {
                "model_id": self.candidate_model_id,
                "output_text": safe_cand_out,
                "latency_ms": cand_latency_ms,
                "prompt_tokens": prompt_tokens,
                "candidate_tokens": candidate_tokens,
                "finish_reason": finish_reason,
                "cost_usd": cost_usd,
                "status": status,
                "error_message": error_message
            }
        }

        # レコード永続化
        self.record_shadow_result(record)
        return record

    def record_shadow_result(self, record: Dict[str, Any]) -> None:
        """
        シャドウレコードをスレッドセーフに JSON Lines ファイルへ追記保存する。
        """
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(line)

    def load_shadow_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        保存されているシャドウレコード一覧を読み出す。
        """
        if not os.path.exists(self.log_file_path):
            return []

        records = []
        with self._lock:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return records

    async def run_blind_ab_test(
        self,
        session_id: str,
        input_text: str,
        conversation_context: List[Dict[str, str]],
        production_output: str,
        production_model_id: str,
        production_latency_ms: int,
        instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Side-by-Side 比較用のブラインド A/B テストデータを生成する。
        - 候補モデルを非同期実行して応答を取得。
        - 位置バイアス（Aを選びがち）を完全に排除するため、50%の確率で A/B の配置をランダムシャッフル。
        - ユーザー投票完了後に正解モデルを開示できるよう reveal_info を保持。
        """
        # 候補モデルを実行（シャドウログにも記録）
        record = await self.execute_shadow(
            session_id=session_id,
            input_text=input_text,
            conversation_context=conversation_context,
            production_output=production_output,
            production_model_id=production_model_id,
            production_latency_ms=production_latency_ms,
            instruction=instruction,
            generation_config=generation_config
        )

        candidate_output = record.get("candidate", {}).get("output_text", "")
        cand_status = record.get("candidate", {}).get("status", "success")

        # 候補モデルでエラーが発生した場合は A/B テスト不可
        if cand_status != "success" or not candidate_output:
            return None

        ab_test_id = str(uuid.uuid4())
        # 位置バイアス防止のためのランダムシャッフル (50% で A=Production, 50% で A=Candidate)
        prod_is_choice_a = random.random() < 0.5

        if prod_is_choice_a:
            choice_a = {"content": production_output, "model_id": production_model_id, "key": "production"}
            choice_b = {"content": candidate_output, "model_id": self.candidate_model_id, "key": "candidate"}
        else:
            choice_a = {"content": candidate_output, "model_id": self.candidate_model_id, "key": "candidate"}
            choice_b = {"content": production_output, "model_id": production_model_id, "key": "production"}

        return {
            "ab_test_id": ab_test_id,
            "session_id": session_id,
            "input_text": input_text,
            "choice_a": choice_a["content"],
            "choice_b": choice_b["content"],
            # クライアントへの開示用マッピング（投票完了後に表示）
            "reveal_info": {
                "A": choice_a["model_id"],
                "B": choice_b["model_id"]
            },
            # 内部判定用（どのキーが選ばれたかの検証）
            "mapping": {
                "A": choice_a["key"],
                "B": choice_b["key"]
            }
        }

    def record_feedback(
        self,
        ab_test_id: str,
        session_id: str,
        selected_choice: str,  # 'A', 'B', 'tie'
        mapping: Dict[str, str],
        user_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ユーザーからの Side-by-Side 投票フィードバックを永続化する。
        """
        feedback_log_path = os.path.join(
            os.path.dirname(self.log_file_path), "feedback_log.jsonl"
        )
        winner_key = "tie"
        if selected_choice in ("A", "B"):
            winner_key = mapping.get(selected_choice, "unknown")

        feedback_record = {
            "feedback_id": str(uuid.uuid4()),
            "ab_test_id": ab_test_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "selected_choice": selected_choice,
            "winner": winner_key,  # 'production' or 'candidate' or 'tie'
            "mapping": mapping,
            "user_comment": user_comment
        }

        line = json.dumps(feedback_record, ensure_ascii=False) + "\n"
        with self._lock:
            with open(feedback_log_path, "a", encoding="utf-8") as f:
                f.write(line)

        return feedback_record

    def get_feedback_summary(self) -> Dict[str, Any]:
        """
        これまでに集まったユーザー投票（A/Bテスト勝率）を集計する。
        """
        feedback_log_path = os.path.join(
            os.path.dirname(self.log_file_path), "feedback_log.jsonl"
        )
        if not os.path.exists(feedback_log_path):
            return {
                "total_votes": 0,
                "production_wins": 0,
                "candidate_wins": 0,
                "ties": 0,
                "candidate_win_rate": 0.0
            }

        total = 0
        prod_wins = 0
        cand_wins = 0
        ties = 0

        with self._lock:
            with open(feedback_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        fb = json.loads(line)
                        total += 1
                        winner = fb.get("winner")
                        if winner == "production":
                            prod_wins += 1
                        elif winner == "candidate":
                            cand_wins += 1
                        elif winner == "tie":
                            ties += 1
                    except json.JSONDecodeError:
                        continue

        cand_win_rate = round(cand_wins / total, 3) if total > 0 else 0.0

        return {
            "total_votes": total,
            "production_wins": prod_wins,
            "candidate_wins": cand_wins,
            "ties": ties,
            "candidate_win_rate": cand_win_rate,
            "production_model": config.GEMINI_MODEL,
            "candidate_model": self.candidate_model_id
        }


# アプリケーション全体で共有されるシングルトンインスタンス
global_shadow_runner = ShadowRunner()
