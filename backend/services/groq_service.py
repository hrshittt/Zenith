"""
Centralized Groq access point — used exclusively by the Tathya chatbot's
agent pipeline (backend/agents/sub_agents.py's Agent.process(), i.e. the
Data/Risk/Compliance/Explainer chain behind every Ask Twin / Tathya chat
reply, reached via POST /twin/chat).

Every other AI call in the backend (Simulation's Recommend/Teach stages,
onboarding extraction, market-sentiment tagging) still goes through
backend/services/gemini_service.py — this file intentionally mirrors that
module's public shape (available()/generate()/generate_json()) so the two
providers are interchangeable from a caller's point of view, but it does not
replace or touch anything Gemini-related.
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

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def _is_rate_limit_error(e: Exception) -> bool:
    """Best-effort detection of rate-limit/quota errors across whatever shape
    the SDK raises (HTTP status code, error code string, or message text)."""
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    if status == 429:
        return True
    err_str = str(e)
    return "429" in err_str or "rate limit" in err_str.lower() or "rate_limit" in err_str.lower()


def _build_client():
    """Lazily construct the Groq client. Returns None if no key is configured
    or the SDK can't be initialized, so callers can fall back gracefully
    instead of crashing (mirrors gemini_service's optional-client behaviour)."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=key)
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {type(e).__name__}")
        return None


class GroqService:
    """Thin wrapper around the Groq SDK used for the Tathya chatbot's
    generation calls. Same generate()/generate_json()/available() interface
    as GeminiService so it's a drop-in for the callers that use it."""

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
        max_output_tokens: int = 2048,
    ) -> str:
        """Generate text (or a JSON string, if json_mode=True). Raises on
        failure so callers can decide how to fall back — never invents a
        response silently."""
        if not self.client:
            raise RuntimeError("Groq client not configured (GROQ_API_KEY missing)")

        messages: List[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        if chat_history:
            for msg in chat_history[-8:]:
                role = "assistant" if msg.get("role") in ("assistant", "twin", "model") else "user"
                text = msg.get("content", "")
                if text:
                    messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Retry on rate-limit errors with a short backoff — mirrors
        # gemini_service.generate()'s resilience so the chatbot degrades the
        # same way regardless of which provider is behind it.
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(**kwargs)
                text = response.choices[0].message.content
                if text is None:
                    raise RuntimeError("Groq returned an empty response")
                return text
            except Exception as e:
                # Log only the error type/message — never the prompt or context,
                # which may contain the user's financial data.
                logger.error(f"Groq generation failed ({GROQ_MODEL}), attempt {attempt + 1}/{max_attempts}: {type(e).__name__}: {e}")
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


# Singleton used by the Tathya chatbot pipeline (backend/agents/sub_agents.py)
# — the one place in the backend that talks to Groq.
groq_service = GroqService()
