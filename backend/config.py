import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip().strip('"\'')
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
