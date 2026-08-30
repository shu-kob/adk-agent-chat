import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip().strip('"\'')
USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1", "yes")
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip().strip('"\'')
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip().strip('"\'')

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash" if USE_VERTEXAI else "gemini-3.5-flash-lite")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
