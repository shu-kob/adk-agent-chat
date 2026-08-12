# ADK Agent Chat

Google Agent Development Kit (ADK) を活用した、React (フロントエンド) + FastAPI (バックエンド) による AI チャットボットアプリケーションです。
AI モデルには Google AI Studio の **`gemini-3.5-flash-lite`** を使用しています。

---

## 🛠 ディレクトリ構成

```text
adk-agent-chat/
├── backend/                # FastAPI (Python) バックエンド
│   ├── agent.py            # Google ADK Agent / Runner / Session 管理
│   ├── config.py           # 環境変数・モデル設定
│   ├── main.py             # FastAPI ルーティング・API エンドポイント
│   ├── requirements.txt    # Python 依存ライブラリ
│   └── .env.example        # 環境変数サンプル
├── frontend/               # React + Vite + TypeScript フロントエンド
│   ├── src/                # UI コンポーネントおよびスタイル
│   ├── package.json        # Node.js 依存ライブラリ
│   └── vite.config.ts      # Vite 設定 (プロキシ設定含む)
└── README.md
```

---

## 🚀 クイックスタートガイド

### 1. バックエンド (FastAPI) の準備と起動

#### (1) 環境変数の設定
`backend` ディレクトリ配下に `.env` ファイルを作成し、Google AI Studio の API キーを設定します。

```bash
cd backend
cp .env.example .env
```

`.env` の内容:
```env
GOOGLE_API_KEY=your_google_ai_studio_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
HOST=0.0.0.0
PORT=8000
```

#### (2) 依存ライブラリのインストール
仮想環境を作成してライブラリをインストールします。

```bash
# 仮想環境作成
python3 -m venv venv
source venv/bin/activate  # macOS / Linux

# パッケージインストール
pip install -r requirements.txt
```

#### (3) バックエンドサーバーの起動

```bash
python3 main.py
# または
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

サーバーが起動すると `http://localhost:8000/api/health` にてヘルスチェックが確認できます。

---

### 2. フロントエンド (React / Vite) の準備と起動

新しいターミナルを開き、`frontend` ディレクトリへ移動して起動します。

#### (1) パッケージのインストール

```bash
cd frontend
npm install
```

#### (2) 開発サーバーの起動

```bash
npm run dev
```

ブラウザで `http://localhost:3000` にアクセスすると、チャットボット UI が表示されます。

---

## 🔌 主な API エンドポイント

| メソッド | パス | 説明 |
| :--- | :--- | :--- |
| `GET` | `/api/health` | バックエンドおよびモデル状態チェック |
| `GET` | `/api/config` | 設定情報（モデル名等）の取得 |
| `POST` | `/api/chat` | メッセージ送信 & AI レスポンス取得 |
| `POST` | `/api/sessions/reset` | 会話セッションのリセット |

---

## 💡 技術スタック

- **Framework (Frontend)**: React 18, Vite, TypeScript
- **Styling**: Vanilla CSS (Modern Dark Mode, Glassmorphism, CSS Variables)
- **Framework (Backend)**: Python 3.10+, FastAPI, Uvicorn
- **AI / Agent Core**: Google Agent Development Kit (`google-adk`), Google Gen AI SDK (`google-genai`)
- **LLM Model**: `gemini-3.5-flash-lite` (Google AI Studio)
