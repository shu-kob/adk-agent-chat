"""
モデル事前疎通・利用可能性チェックモジュール (backend/eval/precheck.py)

【役割】
- ベンチマーク本実行の前に、指定されたモデル識別子が対象の実行環境（Vertex AI または AI Studio）で
  実際に呼び出し可能かを最小リクエスト (ping) で検証する。
- 権限不足 (403) やモデル未提供 (404) 等で利用不能なモデルを事前に除外し、結果表に 0% の無効な行を作らない。
"""

import logging
from typing import List, Tuple, Dict, Any
from google.genai import types

logger = logging.getLogger("eval_precheck")

def validate_model_availability(
    client: Any,
    models: List[str],
    ping_trials: int = 3
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    指定されたモデルリストに対して複数回 (既定3回) の事前疎通リクエスト (Pre-flight check) を送信し、
    利用可能なモデルとスキップ対象のモデルに分類して返却する。
    連続呼び出しでレート制限 (429) が発生しないかも併せて確認する。
    
    :param client: 初期化済みの google.genai.Client インスタンス
    :param models: 検証対象のモデル識別子リスト
    :param ping_trials: 連続疎通試行回数 (既定 3 回)
    :return: (利用可能なモデルIDリスト, スキップされたモデルとエラー情報のリスト)
    """
    valid_models: List[str] = []
    skipped_models: List[Dict[str, str]] = []

    # 最小コスト・最速で応答を確認するための設定
    config = types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=10
    )

    for model_id in models:
        model_ok = True
        last_error = ""

        for trial in range(ping_trials):
            try:
                # 最小の ping メッセージを送信して疎通確認
                resp = client.models.generate_content(
                    model=model_id,
                    contents="ping",
                    config=config
                )
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logger.warning(
                        f"⚠️ モデル '{model_id}' の事前チェック試行 #{trial+1} でレート制限 (429) を検出しました。"
                        f"`EVAL_REQUEST_INTERVAL_SEC` の増加を推奨します。"
                    )
                else:
                    logger.warning(f"モデル '{model_id}' の事前疎通チェックに失敗しました: {error_str}。")
                    model_ok = False
                    break

        if model_ok:
            valid_models.append(model_id)
        else:
            skipped_models.append({
                "model_id": model_id,
                "error": last_error
            })

    return valid_models, skipped_models
