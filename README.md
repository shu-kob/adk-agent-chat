# ADK Agent Chat

Google Agent Development Kit (ADK) を活用した、React + FastAPI による AI チャットボットアプリケーションです。

---

## 📚 ドキュメント一覧

- 📘 **[詳細仕様書 (SPECIFICATION.md)](file:///Users/kobuchishu/programing/adk-agent-chat/SPECIFICATION.md)**: システム設計、API 定義、セッション管理、ベンチマーク仕様
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
- **Evaluation**: 決定論的アサーションエンジン (`backend/eval`)
