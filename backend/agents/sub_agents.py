from typing import Dict, Any, List

from backend.services.gemini_service import gemini_service
from backend.agents.prompts import EXPLAINER_SYSTEM_PROMPT


class Agent:
    def __init__(self, name: str, description: str, system_prompt_override: str = None):
        self.name = name
        self.description = description
        self.system_prompt_override = system_prompt_override

    def process(self, context: Dict[str, Any], instructions: str, chat_history: List[Dict[str, str]] = None) -> str:
        if not gemini_service.available():
            return f"[{self.name}] Mock processing for: {instructions[:30]}..."

        sys_prompt = self.system_prompt_override or f"You are the {self.name} Agent.\nDescription: {self.description}"
        user_prompt = f"Context:\n{context}\n\nTask:\n{instructions}"

        try:
            return gemini_service.generate(
                user_prompt,
                system_instruction=sys_prompt,
                chat_history=chat_history,
                temperature=0.4,
            )
        except Exception as e:
            return f"[{self.name}] Error invoking LLM: {str(e)}"


# Define the sub-agents
data_agent = Agent("Data", "Fetches and normalizes the user's private data and live external data (Market Intelligence).")
risk_agent = Agent("Risk", "Runs financial projection/simulation logic given the gathered data. Explicitly factor in macroeconomic data like inflation, interest rates, and market performance in your projections.")
compliance_agent = Agent("Compliance", "Checks the draft recommendation against basic guardrails.")
explainer_agent = Agent(
    name="Explainer",
    description="Converts the raw simulation output into the final structured, human-readable response.",
    system_prompt_override=EXPLAINER_SYSTEM_PROMPT
)
