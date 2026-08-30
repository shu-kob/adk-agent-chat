# ADK Agent Chat

Google Agent Development Kit (ADK) を活用した、React + FastAPI による AI チャットボットアプリケーションです。

---

## 📚 ドキュメント一覧

- 📘 **[詳細仕様書 (docs/SPECIFICATION.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION.md)**: システム設計、API 定義、セッション管理、ベンチマーク仕様
- 📗 **[評価基盤再設計 追補仕様 v1 (docs/SPECIFICATION_ADDENDUM_v1.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v1.md)**: 測定信頼性確保・データセット拡充・トラフィックリプレイ基盤
- 📗 **[仕様書整合性修正 追補仕様 v2 (docs/SPECIFICATION_ADDENDUM_v2.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v2.md)**: 仕様書整合性の修正と構成整理
- 📗 **[実装確認事項 追補仕様 v3 (docs/SPECIFICATION_ADDENDUM_v3.md)](file:///Users/kobuchishu/programing/adk-agent-chat/docs/SPECIFICATION_ADDENDUM_v3.md)**: 実装確認事項 (ADK Runner非同期実行 & 差分指標設計意図)
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
