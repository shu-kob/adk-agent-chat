"""
トラフィックリプレイ実行ジョブモジュール (backend/eval/traffic/replay.py)

【役割】
- 蓄積された実対話ログからクエリを抽出し、指定された N 個の候補（モデル、プロンプト、生成パラメータ）で
  一括して応答を再生成（リプレイ）する。
- 1回のジョブで 3 候補以上の比較評価をサポートする。
- Phase 1.4 スキーマに完全互換な出力レコードを生成し、`source="replay"` および `candidate_id` を付与して永続化する。
- 実行件数・消費トークン数・所要時間・概算コストを正確に集計・記録する。
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types

from eval.guard import compute_instruction_hash, DATASET_VERSION, EVALUATOR_VERSION, get_sdk_versions
from eval.runner import MODEL_PRICING, calculate_cost
from eval.traffic.store import TrafficStore, global_traffic_store

@dataclass
class ReplayCandidate:
    """
    リプレイ評価対象の候補定義データクラス
    
    モデル単体のみならず、プロンプトやパラメータの異なる組み合わせを
    単一の candidate_id で識別・比較できるようにする。
    """
    candidate_id: str                          # 候補の一意識別子 (例: 'cand_3.7_flash')
    model_id: str                              # Gemini モデル識別子
    instruction: str                           # システムインストラクション
    generation_config: Dict[str, Any] = field(default_factory=dict)  # 生成パラメータ (temperature, max_output_tokens 等)

def generate_replay_content(
    client: Optional[genai.Client],
    model: str,
    prompt: str,
    conversation_context: List[Dict[str, str]],
    instruction: str,
    generation_config: Dict[str, Any],
    timeout_sec: float = 30.0
) -> Tuple[str, int, int]:
    """
    会話コンテキストを付与して Gemini モデルからリプレイ応答を生成する。
    
    :param client: google.genai.Client インスタンス
    :param model: モデル名
    :param prompt: ユーザー入力プロンプト
    :param conversation_context: 直前までの会話履歴リスト
    :param instruction: システムインストラクション
    :param generation_config: temperature, max_output_tokens などの設定辞書
    :param timeout_sec: タイムアウト秒数
    :return: (生成テキスト, 入力トークン数, 出力トークン数)
    """
    if client is None:
        return "Mock replayed response", 50, 20

    temp = generation_config.get("temperature", 0.0)
    seed = generation_config.get("seed", 42)
    max_tokens = generation_config.get("max_output_tokens", 1024)

    config = types.GenerateContentConfig(
        temperature=temp,
        seed=seed,
        max_output_tokens=max_tokens,
        system_instruction=instruction
    )

    # 会話履歴がある場合はプロンプトの先頭にコンテキストを連結
    full_prompt_parts = []
    if conversation_context:
        full_prompt_parts.append("【過去の会話履歴】")
        for msg in conversation_context:
            role = "ユーザー" if msg.get("role") == "user" else "アシスタント"
            full_prompt_parts.append(f"{role}: {msg.get('text', '')}")
        full_prompt_parts.append("\n【現在のユーザー入力】")
    full_prompt_parts.append(prompt)

    merged_prompt = "\n".join(full_prompt_parts)

    response = client.models.generate_content(
        model=model,
        contents=merged_prompt,
        config=config
    )
    text = response.text if response.text else ""
    prompt_tokens = 0
    candidate_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        candidate_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    return text, prompt_tokens, candidate_tokens


class ReplayJob:
    """
    蓄積ログに対する N 候補一括バッチリプレイ実行ジョブクラス
    """
    def __init__(
        self,
        traffic_store: Optional[TrafficStore] = None,
        candidates: Optional[List[ReplayCandidate]] = None,
        client: Optional[genai.Client] = None
    ):
        """
        初期化メソッド
        
        :param traffic_store: 蓄積ログを読み出す TrafficStore インスタンス
        :param candidates: 比較評価する ReplayCandidate のリスト (3候補以上推奨)
        :param client: google.genai.Client インスタンス (省略時は None でモックまたは内部生成)
        """
        self.traffic_store = traffic_store or global_traffic_store
        self.candidates = candidates or []
        self.client = client

    def run(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        sample_ratio: Optional[float] = None,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        指定条件で蓄積ログからクエリを抽出し、全候補モデルでリプレイを実行する。
        
        :param start_time: 抽出開始日時
        :param end_time: 抽出終了日時
        :param limit: 処理する最大クエリ件数
        :param sample_ratio: サンプリング比率
        :param seed: 乱数シード値
        :return: 実行サマリーおよび全試行レコードを含む辞書
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_start_dt = datetime.now()
        job_start_iso = job_start_dt.isoformat()

        # 1. 蓄積ストアからのクエリ抽出
        queries = self.traffic_store.query_interactions(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            sample_ratio=sample_ratio,
            seed=seed
        )

        total_queries = len(queries)
        records: List[Dict[str, Any]] = []

        total_prompt_tokens = 0
        total_candidate_tokens = 0
        total_cost_usd = 0.0

        # 2. 全クエリ × 全候補のリプレイ実行ループ
        for q_idx, query in enumerate(queries, start=1):
            query_id = query.get("query_id", f"q_{q_idx}")
            input_text = query.get("input_text", "")
            context = query.get("conversation_context", [])
            orig_output = query.get("output_text", "")
            orig_model_id = query.get("model_id", "")

            for cand in self.candidates:
                start_t = time.time()
                status = "success"
                error_type = None
                raw_output = ""
                p_tokens = 0
                c_tokens = 0

                try:
                    raw_output, p_tokens, c_tokens = generate_replay_content(
                        client=self.client,
                        model=cand.model_id,
                        prompt=input_text,
                        conversation_context=context,
                        instruction=cand.instruction,
                        generation_config=cand.generation_config
                    )
                except Exception as e:
                    status = "error"
                    error_type = type(e).__name__
                    raw_output = f"Replay API Error: {str(e)}"

                latency_ms = int((time.time() - start_t) * 1000)
                cost_usd = calculate_cost(cand.model_id, p_tokens, c_tokens)

                total_prompt_tokens += p_tokens
                total_candidate_tokens += c_tokens
                total_cost_usd += cost_usd

                # Phase 1.4 + Phase 3 互換レコードの構築
                rec: Dict[str, Any] = {
                    "source": "replay",
                    "job_id": job_id,
                    "query_id": query_id,
                    "candidate_id": cand.candidate_id,
                    "model_id": cand.model_id,
                    "provider_route": "vertex_ai",
                    "instruction_hash": compute_instruction_hash(cand.instruction),
                    "generation_config": cand.generation_config,
                    "status": status,
                    "error_type": error_type,
                    "latency_ms": latency_ms,
                    "input_text": input_text,
                    "original_output": orig_output,
                    "original_model_id": orig_model_id,
                    "raw_output": raw_output,
                    "prompt_tokens": p_tokens,
                    "candidate_tokens": c_tokens,
                    "cost_usd": cost_usd,
                    "dataset_version": DATASET_VERSION,
                    "evaluator_version": EVALUATOR_VERSION,
                    "sdk_versions": get_sdk_versions()
                }
                records.append(rec)

        job_end_dt = datetime.now()
        job_end_iso = job_end_dt.isoformat()
        total_duration = (job_end_dt - job_start_dt).total_seconds()

        return {
            "job_id": job_id,
            "started_at": job_start_iso,
            "completed_at": job_end_iso,
            "duration_sec": round(total_duration, 2),
            "total_queries_processed": total_queries,
            "total_candidates": len(self.candidates),
            "total_records": len(records),
            "total_prompt_tokens": total_prompt_tokens,
            "total_candidate_tokens": total_candidate_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "records": records
        }
