import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
import os
import config

logger = logging.getLogger("adk_agent")

try:
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    logger.warning("google-adk package not found. Falling back to google-genai direct SDK interface.")

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-genai package not found.")


class ChatAgentManager:
    """
    Manages the Google ADK Agent instance, runner, and session lifecycle.
    """
    def __init__(self, model_name: str = config.GEMINI_MODEL):
        self.model_name = model_name
        self.session_service = None
        self.runner = None
        self.adk_agent = None
        self._init_adk()

    def _init_adk(self):
        if ADK_AVAILABLE:
            try:
                # Initialize ADK LlmAgent
                self.adk_agent = LlmAgent(
                    name="chat_assistant",
                    model=self.model_name,
                    instruction=(
                        "You are a helpful, friendly, and highly intelligent AI assistant powered by "
                        f"Google ADK and Gemini ({self.model_name}). "
                        "Respond concisely and accurately in markdown format when appropriate."
                    )
                )
                self.session_service = InMemorySessionService()
                self.runner = Runner(
                    agent=self.adk_agent,
                    app_name="adk_chat_app",
                    session_service=self.session_service
                )
                logger.info(f"Successfully initialized ADK Agent with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize ADK Agent: {e}")
                ADK_AVAILABLE_LOCAL = False

    async def get_or_create_session(self, session_id: str, user_id: str = "default_user"):
        if ADK_AVAILABLE and self.session_service:
            try:
                # Check if get_session is coroutine or normal method
                res = self.session_service.get_session(
                    app_name="adk_chat_app",
                    user_id=user_id,
                    session_id=session_id
                )
                session = await res if asyncio.iscoroutine(res) else res

                if not session:
                    res_create = self.session_service.create_session(
                        app_name="adk_chat_app",
                        user_id=user_id,
                        session_id=session_id
                    )
                    session = await res_create if asyncio.iscoroutine(res_create) else res_create
                return session
            except Exception as e:
                logger.error(f"Error fetching/creating session {session_id}: {e}")
        return None

    async def generate_response(self, session_id: str, prompt: str, user_id: str = "default_user") -> str:
        """
        Processes a user message and returns the complete text response.
        """
        if not config.USE_VERTEXAI and not config.GOOGLE_API_KEY:
            return (
                "⚠️ Authentication missing. Please set `GOOGLE_API_KEY` for AI Studio, "
                "or set `GOOGLE_GENAI_USE_VERTEXAI=true` and run `gcloud auth application-default login`."
            )

        # 1. Try ADK Runner first if available
        if ADK_AVAILABLE and self.runner:
            try:
                await self.get_or_create_session(session_id=session_id, user_id=user_id)
                response_text = ""
                # Execute agent via runner
                run_res = self.runner.run(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=prompt
                )
                events = await run_res if asyncio.iscoroutine(run_res) else run_res

                if isinstance(events, str):
                    return events

                if hasattr(events, "__aiter__"):
                    async for event in events:
                        if hasattr(event, "content") and event.content:
                            response_text += str(event.content)
                        elif hasattr(event, "text"):
                            response_text += str(event.text)
                elif hasattr(events, "__iter__"):
                    for event in events:
                        if hasattr(event, "content") and event.content:
                            response_text += str(event.content)
                        elif hasattr(event, "text"):
                            response_text += str(event.text)

                if response_text:
                    return response_text
            except Exception as e:
                logger.warning(f"ADK runner execution encounter: {e}. Falling back to direct client.")

        # 2. Fallback to google-genai SDK direct client call
        if GENAI_AVAILABLE:
            try:
                if config.USE_VERTEXAI:
                    client = genai.Client(
                        vertexai=True,
                        project=config.GCP_PROJECT,
                        location=config.GCP_LOCATION
                    )
                else:
                    client = genai.Client(api_key=config.GOOGLE_API_KEY)

                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text if response.text else "No response generated."
            except Exception as e:
                logger.error(f"GenAI SDK execution error: {e}")
                return f"Error communicating with Gemini ({self.model_name}): {str(e)}"

        return "Error: Neither google-adk nor google-genai could process the request."

    async def clear_session(self, session_id: str, user_id: str = "default_user") -> bool:
        """
        Clears/deletes the session state.
        """
        if ADK_AVAILABLE and self.session_service:
            try:
                res = self.session_service.delete_session(
                    app_name="adk_chat_app",
                    user_id=user_id,
                    session_id=session_id
                )
                if asyncio.iscoroutine(res):
                    await res
                return True
            except Exception as e:
                logger.error(f"Error clearing session {session_id}: {e}")
        return True

# Singleton instance
agent_manager = ChatAgentManager()
