"""
Shadow Testing 実験・デモ実行スクリプト (backend/eval/traffic/run_shadow_demo.py)

【使い方】
python backend/eval/traffic/run_shadow_demo.py

本番モデルと候補モデルに対して数件のサンプルクエリを並行・非同期（シャドウテスト）で流し、
ログ蓄積と差分分析レポートをターミナルに表示します。
"""

import os
import sys
import asyncio
import time

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import config
from eval.traffic.shadow import ShadowRunner
from eval.traffic.diff_analyzer import compute_shadow_diff_metrics, generate_shadow_diff_report
from agent import agent_manager


# 実験用サンプルクエリ
SAMPLE_QUERIES = [
    "こんにちは！あなたの得意なことや主な機能を簡潔に教えてください。",
    "Pythonで非同期処理（asyncio）を使うメリットを3点箇条書きで教えてください。",
    "日本の首都と、有名な観光名所を2つ挙げてください。",
]


async def run_experiment():
    # 候補モデルの設定: gemini-3.8-flash
    prod_model = config.GEMINI_MODEL
    cand_model = getattr(config, "SHADOW_MODEL_ID", "gemini-3.8-flash")

    demo_log_path = os.path.join(os.path.dirname(__file__), "data", "shadow_demo_log.jsonl")
    if os.path.exists(demo_log_path):
        os.remove(demo_log_path)

    runner = ShadowRunner(
        enabled=True,
        candidate_model_id=cand_model,
        sample_rate=1.0,
        log_file_path=demo_log_path
    )

    print("=" * 70)
    print("🚀 Shadow Testing 実験開始")
    print(f"・本番モデル (Production) : {prod_model}")
    print(f"・候補モデル (Candidate)  : {cand_model}")
    print(f"・サンプルクエリ件数       : {len(SAMPLE_QUERIES)} 件")
    print(f"・ログ出力先               : {demo_log_path}")
    print("=" * 70)

    shadow_tasks = []

    for i, query in enumerate(SAMPLE_QUERIES, 1):
        session_id = f"demo-session-{i}"
        print(f"\n[{i}/{len(SAMPLE_QUERIES)}] ユーザー入力: 「{query}」")

        # 1. 本番モデルでの応答生成 (同期計測)
        start_t = time.time()
        print("  ⏳ 本番モデルで応答生成中...")
        prod_reply = await agent_manager.generate_response(
            session_id=session_id,
            prompt=query
        )
        prod_latency_ms = int((time.time() - start_t) * 1000)
        print(f"  ✅ 本番応答完了 ({prod_latency_ms} ms)")
        print(f"     本番応答抜粋: {prod_reply[:60].replace(chr(10), ' ')}...")

        # 2. 候補モデルのシャドウテストを非同期スケジュール
        print(f"  👥 候補モデル ({cand_model}) へシャドウテストを非同期キック...")
        task = runner.schedule_shadow(
            session_id=session_id,
            input_text=query,
            conversation_context=[],
            production_output=prod_reply,
            production_model_id=prod_model,
            production_latency_ms=prod_latency_ms
        )
        if task:
            shadow_tasks.append(task)

    # 全シャドウタスクの完了を待機
    if shadow_tasks:
        print("\n⏳ バックグラウンドで走っている全シャドウタスクの完了を待機中...")
        await asyncio.gather(*shadow_tasks)
        print("✅ 全シャドウタスクの実行完了！\n")

    # 3. ログの集計とレポート出力
    records = runner.load_shadow_records()
    metrics = compute_shadow_diff_metrics(records)
    report_md = generate_shadow_diff_report(metrics)

    print("=" * 70)
    print(report_md)
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_experiment())
