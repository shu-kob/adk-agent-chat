"""
評価実行メタデータ、バージョン追跡 & マージガードモジュール (backend/eval/guard.py)

【役割】
- 評価の各試行レコードに対して、18項目に及ぶ厳密な実行メタデータ（ハッシュ、SDKバージョン、パラメータ等）を付与する。
- 異なる実行経路（Vertex AI vs AI Studio）やインストラクションハッシュの結果を誤って単一マトリクスに統合することを防ぐ「マージガード (MergeGuard)」を提供する。
"""

import hashlib
import importlib.metadata
from typing import Dict, Any, List, Optional

# データセットおよび採点エンジンのバージョン識別子
DATASET_VERSION: str = "v2.0.0"
EVALUATOR_VERSION: str = "v2.0.0"

class MergeGuardViolationError(ValueError):
    """
    実行環境、プロバイダルート、インストラクションハッシュ、データセットバージョンが異なる
    互換性のない評価レコードを単一マトリクスに統合しようとした際に送出される例外。
    """
    pass

def compute_instruction_hash(instruction: str) -> str:
    """
    システムインストラクション文字列の SHA-256 ハッシュを計算し、先頭 12 文字を返す。
    プロンプト変更をまたいだ無効な比較を防ぐために使用する。
    
    :param instruction: システムプロンプト/指示テキスト
    :return: ハッシュ文字列 (12文字)
    """
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:12]

def get_sdk_versions() -> Dict[str, str]:
    """
    実行環境にインストールされている主要 Google SDK (`google-genai`, `google-adk`) のバージョン辞書を取得する。
    
    :return: {"google_genai": "x.y.z", "google_adk": "x.y.z"} 形式の辞書
    """
    versions = {}
    for pkg, key in [("google-genai", "google_genai"), ("google-adk", "google_adk")]:
        try:
            versions[key] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[key] = "not_installed"
    return versions

def create_trial_record(
    run_id: str,
    trial_index: int,
    case_id: str,
    category: str,
    model_id: str,
    provider_route: str,
    location: Optional[str],
    execution_path: str,
    instruction: str,
    generation_config: Dict[str, Any],
    status: str,
    error_type: Optional[str],
    latency_ms: int,
    score: Optional[float],
    raw_output: str,
    title: Optional[str] = None,
    eval_type: Optional[str] = None,
    prompt_tokens: int = 0,
    candidate_tokens: int = 0,
    cost_usd: float = 0.0,
    reasons: Optional[List[str]] = None,
    assertions: Optional[List[Dict[str, Any]]] = None,
    retry_count: int = 0,
    finish_reason: Optional[str] = None,
    truncated: Optional[bool] = None,
    truncation_type: Optional[str] = None,
    thinking_tokens: Optional[int] = None,
    usage_raw: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    SPECIFICATION_ADDENDUM_v1 & v4 & v5 & v6 スキーマに準拠した、単一試行レコード (1行) を構築する。
    
    【特徴】
    - status="error" の場合、score は 0 ではなく None (null) として記録され、成功ケースと明確に分離される。
    - N候補モデルへの拡張が容易な行指向のフラット構造。
    - v4: retry_count の記録に対応。
    - v5: finish_reason, truncated, thinking_tokens, usage_raw の記録に対応。
    - v6: truncation_type (thinking_dominant / output_dominant / unknown) の記録に対応。
    
    :param run_id: 実行バッチの一意識別子
    :param trial_index: 同一ケース・モデル内での試行番号 (0-origin)
    :param case_id: 評価ケースID (例: 'struct_01')
    :param category: 評価カテゴリ (例: 'structured_output')
    :param model_id: 完全なモデルバージョン文字列
    :param provider_route: 実行経路 ('vertex_ai' または 'ai_studio')
    :param location: リージョン名 (Vertex AI の場合)
    :param execution_path: エージェント実行経路 ('adk' または 'genai_sdk_direct')
    :param instruction: 使用されたシステムインストラクション
    :param generation_config: temperature, seed, max_output_tokens などのパラメータ辞書
    :param status: 実行ステータス ('success' または 'error')
    :param error_type: エラー発生時の例外種別 (成功時は None)
    :param latency_ms: 応答所要時間 (ミリ秒)
    :param score: 採点スコア (0.0〜1.0, エラー時は None)
    :param raw_output: モデルの生出力文字列
    :param title: テストケースのタイトル
    :param eval_type: 評価タイプ
    :param prompt_tokens: 入力トークン数
    :param candidate_tokens: 出力トークン数
    :param cost_usd: 概算コスト (USD)
    :param reasons: 採点理由メッセージリスト
    :param assertions: アサーション単位の合否詳細リスト
    :param retry_count: リトライ回数
    :param finish_reason: APIが返した生の停止理由 (例: 'STOP', 'MAX_TOKENS')
    :param truncated: トークン上限による打ち切りが発生したか否か
    :param truncation_type: 打ち切りの種別 ('thinking_dominant' / 'output_dominant' / 'unknown' / None)
    :param thinking_tokens: 内部推論 (Thinking) に消費されたトークン数
    :param usage_raw: APIレスポンスの usage_metadata 生辞書
    :return: 完全な試行レコード辞書
    """
    is_error = (status == "error")

    record: Dict[str, Any] = {
        "run_id": run_id,
        "trial_index": trial_index,
        "case_id": case_id,
        "category": category,
        "title": title or case_id,
        "eval_type": eval_type,
        "model_id": model_id,
        "provider_route": provider_route,
        "location": location,
        "execution_path": execution_path,
        "instruction_hash": compute_instruction_hash(instruction),
        "dataset_version": DATASET_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "sdk_versions": get_sdk_versions(),
        "generation_config": generation_config,
        "status": status,
        "error_type": error_type,
        "latency_ms": latency_ms,
        "score": None if is_error else score,
        "raw_output": raw_output,
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "thinking_tokens": thinking_tokens,
        "finish_reason": finish_reason,
        "truncated": truncated,
        "truncation_type": truncation_type,
        "usage_raw": usage_raw,
        "cost_usd": cost_usd,
        "retry_count": retry_count,
        "reasons": reasons or [],
        "assertions": assertions or []
    }
    return record


class MergeGuard:
    """
    集計時に、比較不能な異なる環境・バージョンのレコードが単一の比較マトリクスに
    混入・統合されることを防ぐバリデータークラス。
    """
    # 一致していなければならない必須ガードフィールド一覧
    GUARD_FIELDS = [
        "provider_route",
        "instruction_hash",
        "dataset_version",
        "evaluator_version"
    ]

    @classmethod
    def validate_mergeable(cls, records: List[Dict[str, Any]]) -> bool:
        """
        全レコードのガードフィールドが完全に一致しているかを検証する。
        不一致を発見した場合は MergeGuardViolationError を送出して処理を中断する。
        
        :param records: 検証対象の試行レコードリスト
        :return: True (全レコードが整合している場合)
        :raises MergeGuardViolationError: 異なる実行環境やハッシュが混在している場合
        """
        if not records:
            return True

        base_record = records[0]
        for idx, rec in enumerate(records[1:], start=1):
            for field in cls.GUARD_FIELDS:
                base_val = base_record.get(field)
                rec_val = rec.get(field)
                if base_val != rec_val:
                    raise MergeGuardViolationError(
                        f"MergeGuard Violation at record {idx}: '{field}' 不一致 "
                        f"('{base_val}' vs '{rec_val}')。異なる実行環境・ハッシュの結果を単一表に統合することはできません。"
                    )
        return True
