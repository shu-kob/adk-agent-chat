# ADK Agent Chat

Google Agent Development Kit (ADK) を活用した、React + FastAPI による AI チャットボットアプリケーションです。

---

## 📚 ドキュメント一覧

- 📘 **[詳細仕様書 (docs/SPECIFICATION.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION.md)**: システム設計、API 定義、セッション管理、ベンチマーク仕様
- 👥 **[Shadow Testing 仕様書 (docs/SHADOW_TESTING.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SHADOW_TESTING.md)**: オンライン・シャドウテストのアーキテクチャ図、API、運用仕様
- 📊 **[Shadow Testing 実験インサイト (docs/SHADOW_TESTING_INSIGHTS.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SHADOW_TESTING_INSIGHTS.md)**: 実トラフィック検証ログ、モデル選好の逆転劇、ルーティング知見
- 📗 **[評価基盤再設計 追補仕様 v1 (docs/SPECIFICATION_ADDENDUM_v1.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v1.md)**: 測定信頼性確保・データセット拡充・トラフィックリプレイ基盤
- 📗 **[仕様書整合性修正 追補仕様 v2 (docs/SPECIFICATION_ADDENDUM_v2.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v2.md)**: 仕様書整合性の修正と構成整理
- 📗 **[実装確認事項 追補仕様 v3 (docs/SPECIFICATION_ADDENDUM_v3.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v3.md)**: 実装確認事項 (ADK Runner非同期実行 & 差分指標設計意図)
- 📗 **[測定カバレッジとレート制限対応 追補仕様 v4 (docs/SPECIFICATION_ADDENDUM_v4.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v4.md)**: 測定カバレッジ・指数バックオフ・共通マトリクス・失敗分布
- 📊 **[モデル評価レポート (eval_matrix_analysis.md)](file:///Users/kobuchishu/programing/adk-agent-chat/backend/eval/results/eval_matrix_analysis.md)**: Gemini 各世代の評価マトリクスと性能考察

---

## 🚀 クイックスタート

### 1. バックエンド起動 (FastAPI)

```bash
cd backend
cp .env.example .env  # GOOGLE_API_KEY または Vertex AI 設定を入力
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```
> `http://localhost:8000/api/health` でヘルスチェックが確認できます。

### 2. フロントエンド起動 (React)

```bash
cd frontend
npm install
npm run dev
```
> `http://localhost:3000` にアクセスしてチャットを開始できます。

---

## 💡 技術スタック概要

- **Frontend**: React 18, TypeScript, Vite, Vanilla CSS (Dark Mode)
- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **AI Core**: Google Agent Development Kit (`google-adk`), Google Gen AI SDK (`google-genai`)
- **Evaluation & Replay**: 決定論的アサーション評価基盤 & 実トラフィック蓄積・リプレイ分析基盤 (`backend/eval`)

---

## 🔒 実トラフィック蓄積と個人情報保護 (Phase 3)
本アプリケーションでは、モデル比較・継続的評価（リプレイ分析）を目的として `/api/chat` の対話ログを `backend/eval/traffic/data/traffic_log.jsonl` に自動蓄積します。
保存時には `default_pii_masking_hook` により、メールアドレス (`[EMAIL]`) や電話番号 (`[PHONE]`) などの個人識別情報 (PII) を自動マスキングして保存します。

---

## 👥 実装済み: Shadow Testing & ブラインド A/B 評価基盤

新モデルの導入やプロンプト変更を安全・確実に検証するため、以下の Shadow Testing および評価機能を実装済みです。

### 1. 本番影響ゼロの非同期トラフィックミラーリング (`backend/eval/traffic/shadow.py`)
- **遅延 0ms で即時返却**: 本番モデル（例: `gemini-3.7-flash`）の応答を即座にクライアントへ返却し、候補モデル（例: `gemini-3.8-flash`）の実行は `asyncio.create_task` で完全非同期にバックグラウンド実行。
- **障害隔離 & 自動フェイルオーバー**: 候補モデル側のエラーや 429 Quota Exhausted（レート制限）を本番ユーザーに一切波及させず、安全なフォールバックモデル（`gemini-3.5-flash-lite` 等）へ自動切り替え。
- **PII マスキングログ保存**: 個人情報をマスクした上で `backend/eval/traffic/data/shadow_log.jsonl` へ安全に構造化ログを記録。

### 2. ブラインド Side-by-Side A/B テスト UI (`frontend/src/components/SideBySideComparison.tsx`)
- **位置バイアス排除のランダムシャッフル**: 人間が無意識に左側の回答を選びやすい偏り（Position Bias）を防ぐため、50% の確率で回答 A / 回答 B の配置を入れ替えて提示。
- **ブラインド比較 & 投票後の開示 (Reveal)**: モデル名を伏せた状態でユーザーに比較・投票させ、投票後に正解のモデル名（例: 🏆 回答 A = `gemini-3.7-flash`）を開示。
- **フィードバック集計 API**: ユーザーの好みの投票ログ (`feedback_log.jsonl`) を蓄積し、勝率や選好傾向を集計する `/api/eval/feedback/summary` を提供。
- **A/B テスト出現頻度の制御**: ヘッダーから「自動（時々出現）」「常時オン ⚡️」「オフ」を即座に切り替え可能。

### 3. Gemini Batch API 連携とコスト削減（FinOps） (`backend/eval/traffic/batch.py`)
- **50% OFF のバッチ推論用エクスポート**: 実トラフィックログから、Gemini Batch API（夜間バッチや非同期一括評価で通常料金の半額）へ投入可能な JSONL ファイルを自動生成。
- **FinOps コスト試算 API**: オンデマンド実行時と Batch API 実行時の差額を即座に計算する `/api/eval/batch/finops` を提供。

### 4. 決定論的差分分析ツール (`backend/eval/traffic/diff_analyzer.py`)
- 本番モデルと候補モデルの応答文字数比率、レーベンシュタイン距離による類似度、レイテンシ比較、A/B テスト勝率サマリレポートを自動算出。

