import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import config
from agent import agent_manager

app = FastAPI(
    title="ADK Agent Chat API",
    description="FastAPI backend for Google Agent Development Kit (ADK) Chatbot using Gemini-3.5-Flash-Lite",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., description="User prompt or message content", example="Hello! What can you do?")
    session_id: Optional[str] = Field(default=None, description="Unique session ID for conversation memory")
    user_id: Optional[str] = Field(default="default_user", description="User identifier")

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model: str

class ResetSessionRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = Field(default="default_user")

class ResetSessionResponse(BaseModel):
    status: str
    session_id: str

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "model": config.GEMINI_MODEL,
        "adk_agent": "initialized"
    }

@app.get("/api/config")
async def get_config():
    has_api_key = bool(config.GOOGLE_API_KEY)
    return {
        "model": config.GEMINI_MODEL,
        "has_api_key": has_api_key
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty."
        )

    session_id = request.session_id or str(uuid.uuid4())
    user_id = request.user_id or "default_user"

    reply = await agent_manager.generate_response(
        session_id=session_id,
        prompt=request.message.strip(),
        user_id=user_id
    )

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        model=config.GEMINI_MODEL
    )

@app.post("/api/sessions/reset", response_model=ResetSessionResponse)
async def reset_session_endpoint(request: ResetSessionRequest):
    await agent_manager.clear_session(session_id=request.session_id, user_id=request.user_id or "default_user")
    return ResetSessionResponse(
        status="session_cleared",
        session_id=request.session_id
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
