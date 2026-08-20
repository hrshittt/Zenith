"""
Centralized Gemini access point.

Every LLM/RAG/agent-generation call in the backend (Ask Twin's agent
pipeline, Simulation's Recommend/Teach stages, onboarding extraction,
market-sentiment tagging) goes through this module instead of calling a
provider SDK directly. That keeps the API key server-side only, keeps
generation parameters consistent, and makes a future provider swap a
one-file change.
"""
import os
import re
import json
import time
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def _is_rate_limit_error(e: Exception) -> bool:
    """Best-effort detection of rate-limit/quota errors across whatever shape
    the SDK raises (HTTP status code, error code string, or message text)."""
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    if status == 429:
        return True
    err_str = str(e)
    return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower()


def _build_client():
    """Lazily construct the Gemini client. Returns None if no key is configured
    or the SDK can't be initialized, so callers can fall back gracefully
    instead of crashing (mirrors the previous Groq-optional behaviour)."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=key)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {type(e).__name__}")
        return None


class GeminiService:
    """Thin wrapper around the Gemini SDK used for every generation task."""

    def __init__(self):
        self._client = None
        self._init_attempted = False

    @property
    def client(self):
        if not self._init_attempted:
            self._client = _build_client()
            self._init_attempted = True
        return self._client

    def available(self) -> bool:
        return self.client is not None

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        json_mode: bool = False,
        temperature: float = 0.4,
        max_output_tokens: int = 512,
    ) -> str:
        """Generate text (or a JSON string, if json_mode=True). Raises on
        failure so callers can decide how to fall back — never invents a
        response silently."""
        if not self.client:
            raise RuntimeError("Gemini client not configured (GEMINI_API_KEY missing)")

        from google.genai import types

        contents = []
        if chat_history:
            for msg in chat_history[-8:]:
                role = "model" if msg.get("role") in ("assistant", "twin", "model") else "user"
                text = msg.get("content", "")
                if text:
                    contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "thinking_config": types.ThinkingConfig(thinking_budget=1),
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        # Retry on rate-limit errors with a short backoff — centralized here
        # so every caller (Ask Twin agents, Simulation, onboarding) gets the
        # same resilience without duplicating retry logic.
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config,
                )
                text = response.text
                if text is None:
                    raise RuntimeError("Gemini returned an empty response")
                return text
            except Exception as e:
                # Log only the error type/message — never the prompt or context,
                # which may contain the user's financial data.
                logger.error(f"Gemini generation failed ({GEMINI_MODEL}), attempt {attempt + 1}/{max_attempts}: {type(e).__name__}: {e}")
                if _is_rate_limit_error(e) and attempt < max_attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> Optional[Dict[str, Any]]:
        """Generate and parse a JSON object. Returns None on failure instead
        of raising, since JSON-mode callers usually have a deterministic
        fallback path."""
        try:
            text = self.generate(
                prompt,
                system_instruction=system_instruction,
                json_mode=True,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception:
            return None

        try:
            return json.loads(text)
        except Exception:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return None
        return None


# Singleton used across the app — the one place that talks to Gemini.
gemini_service = GeminiService()
