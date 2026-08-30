"""
実トラフィック蓄積・マスキングモジュール (backend/eval/traffic/store.py)

【役割】
- 本番対話 API (`/api/chat`) の入出力データを非同期・スレッドセーフに JSON Lines 形式で永続化する。
- リプレイに必要な直前までの会話コンテキスト (`conversation_context`) を保持する。
- 個人情報（PII: メールアドレス・電話番号等）のマスキングフック機能を提供する。
- 期間、件数上限、サンプリング率による柔軟な抽出クエリ機能を提供する。
"""

import os
import json
import re
import uuid
import random
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from eval.guard import compute_instruction_hash

# 既定のトラフィックログ保存先
DEFAULT_TRAFFIC_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "data", "traffic_log.jsonl"
)

def default_pii_masking_hook(text: str) -> str:
    """
    個人情報 (PII: メールアドレス, 日本の電話番号) を検出してマスクする既定のフック関数
    
    :param text: マスキング対象の生テキスト
    :return: マスキング適用後のテキスト
    """
    if not text:
        return text

    # メールアドレスのマスキング (例: user@example.com -> [EMAIL])
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    masked = re.sub(email_pattern, "[EMAIL]", text)

    # 電話番号のマスキング (例: 090-1234-5678, 03-1234-5678, 0120-123-456)
    phone_pattern = r"\b0\d{1,4}[-(]?\d{1,4}[-)]?\d{3,4}\b"
    masked = re.sub(phone_pattern, "[PHONE]", masked)

    return masked


class TrafficStore:
    """
    本番トラフィックの蓄積と抽出クエリを管理するストレージクラス
    """
    def __init__(
        self,
        log_file_path: Optional[str] = None,
        masking_hook: Optional[Callable[[str], str]] = None
    ):
        """
        初期化メソッド
        
        :param log_file_path: ログの出力先 JSONL パス (省略時は DEFAULT_TRAFFIC_LOG_PATH)
        :param masking_hook: 個人情報マスキング関数 (省略時はマスキングなし)
        """
        self.log_file_path = log_file_path or DEFAULT_TRAFFIC_LOG_PATH
        self.masking_hook = masking_hook
        self._lock = threading.Lock()
        
        # 保存先ディレクトリの自動作成
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    def record_interaction(
        self,
        session_id: str,
        input_text: str,
        conversation_context: List[Dict[str, str]],
        output_text: str,
        model_id: str,
        provider_route: str,
        instruction: str,
        generation_config: Dict[str, Any],
        latency_ms: int
    ) -> Dict[str, Any]:
        """
        対話ログ 1 件を JSON Lines ファイルに記録する。
        
        :param session_id: 会話セッション識別子
        :param input_text: ユーザー入力テキスト
        :param conversation_context: リプレイに必要な直前までの会話履歴リスト
        :param output_text: モデルが実際に返した応答テキスト
        :param model_id: 使用されたモデルの完全バージョン文字列
        :param provider_route: 'vertex_ai' または 'ai_studio'
        :param instruction: その時点のシステムインストラクション
        :param generation_config: 実際の生成パラメータ (temperature, max_tokens 等)
        :param latency_ms: 応答生成所要時間 (ミリ秒)
        :return: 永続化された蓄積レコード辞書 (11項目)
        """
        # マスキングフックの適用
        safe_input = self.masking_hook(input_text) if self.masking_hook else input_text
        safe_output = self.masking_hook(output_text) if self.masking_hook else output_text
        
        safe_context = []
        for msg in conversation_context:
            c_text = msg.get("text", "")
            safe_c_text = self.masking_hook(c_text) if self.masking_hook else c_text
            safe_context.append({
                "role": msg.get("role", "user"),
                "text": safe_c_text
            })

        query_id = f"qry_{uuid.uuid4().hex[:12]}"
        timestamp_iso = datetime.now().isoformat()
        instruction_hash = compute_instruction_hash(instruction)

        record: Dict[str, Any] = {
            "query_id": query_id,
            "timestamp": timestamp_iso,
            "session_id": session_id,
            "input_text": safe_input,
            "conversation_context": safe_context,
            "output_text": safe_output,
            "model_id": model_id,
            "provider_route": provider_route,
            "instruction_hash": instruction_hash,
            "generation_config": generation_config,
            "latency_ms": latency_ms
        }

        # スレッドセーフにファイル末尾へ追記
        with self._lock:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def query_interactions(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        sample_ratio: Optional[float] = None,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        蓄積された対話ログから、期間指定・件数上限・サンプリング率に基づいてクエリを抽出する。
        
        :param start_time: 抽出開始日時 (省略時は制限なし)
        :param end_time: 抽出終了日時 (省略時は制限なし)
        :param limit: 取得最大件数
        :param sample_ratio: サンプリング抽出比率 (0.0〜1.0)
        :param seed: ランダムサンプリングの乱数シード
        :return: 抽出された蓄積レコードリスト
        """
        if not os.path.exists(self.log_file_path):
            return []

        records: List[Dict[str, Any]] = []
        with self._lock:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        rec_dt = datetime.fromisoformat(rec["timestamp"])

                        # 期間フィルタ
                        if start_time and rec_dt < start_time:
                            continue
                        if end_time and rec_dt > end_time:
                            continue

                        records.append(rec)
                    except Exception:
                        continue

        # サンプリング適用
        if sample_ratio is not None and 0.0 < sample_ratio < 1.0:
            if seed is not None:
                random.seed(seed)
            records = [r for r in records if random.random() < sample_ratio]

        # 件数上限 (limit) 適用
        if limit is not None and limit > 0:
            records = records[:limit]

        return records

# シングルトンインスタンス (個人情報マスキングフック有効)
global_traffic_store = TrafficStore(masking_hook=default_pii_masking_hook)
