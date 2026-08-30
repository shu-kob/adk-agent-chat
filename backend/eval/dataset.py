"""
LLM ベンチマーク評価データセット ローダー (backend/eval/dataset.py)

【役割】
- 評価データセットを Python コード内リテラルから分離し、外部 JSON ファイル (`eval/datasets/benchmark_v2.json`) からロードする。
- バージョン識別子 (`DATASET_VERSION_V2 = "v2.0.0"`) の管理と、`enabled=False` な保留ケースのフィルタリング機能を提供する。
"""

import os
import json
from typing import List, Dict, Any, Optional

# データセットの現在のバージョン識別子 (SPECIFICATION_ADDENDUM_v1 Phase 2 準拠)
DATASET_VERSION_V2: str = "v2.0.0"

# 既定の外部データセット JSON ファイルパス
DEFAULT_DATASET_FILE: str = os.path.join(os.path.dirname(__file__), "datasets", "benchmark_v2.json")

def load_benchmark_dataset(
    file_path: Optional[str] = None,
    include_disabled: bool = False
) -> List[Dict[str, Any]]:
    """
    外部 JSON ファイルからベンチマーク評価ケース一覧を読み込む。
    
    :param file_path: 読み込み対象の JSON ファイルパス (省略時はデフォルトの benchmark_v2.json)
    :param include_disabled: enabled=False の保留ケースを含めて取得するかどうか (デフォルト: False)
    :return: 評価ケース辞書のリスト
    :raises FileNotFoundError: 指定されたファイルが存在しない場合
    """
    target_path = file_path or DEFAULT_DATASET_FILE

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"ベンチマークデータセットファイルが見つかりません: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    if include_disabled:
        return cases

    # enabled: true のケースのみを抽出して返却
    return [c for c in cases if c.get("enabled", True) is True]

# 既存コードとの後方互換性のためのエイリアス
BENCHMARK_CASES = load_benchmark_dataset(include_disabled=False)
