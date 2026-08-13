import os
from typing import Dict, Any, List
from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Mock fallback in case GROQ_API_KEY is not set or valid
def get_groq_client():
    key = os.getenv("GROQ_API_KEY")
    if key:
        try:
            return Groq(api_key=key)
        except Exception:
            return None
    return None

class Agent:
    def __init__(self, name: str, description: str, system_prompt_override: str = None):
        self.name = name
        self.description = description
        self.system_prompt_override = system_prompt_override
        self.client = get_groq_client()

    def process(self, context: Dict[str, Any], instructions: str) -> str:
        if not self.client:
            return f"[{self.name}] Mock processing for: {instructions[:30]}..."
            
        sys_prompt = self.system_prompt_override or f"You are the {self.name} Agent.\nDescription: {self.description}"
        user_prompt = f"Context:\n{context}\n\nTask:\n{instructions}"
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama-3.1-8b-instant",
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[{self.name}] Error invoking LLM: {str(e)}"

from backend.agents.prompts import EXPLAINER_SYSTEM_PROMPT

# Define the sub-agents
data_agent = Agent("Data", "Fetches and normalizes the user's private data and live external data (Market Intelligence).")
risk_agent = Agent("Risk", "Runs financial projection/simulation logic given the gathered data. Explicitly factor in macroeconomic data like inflation, interest rates, and market performance in your projections.")
compliance_agent = Agent("Compliance", "Checks the draft recommendation against basic guardrails.")
explainer_agent = Agent(
    name="Explainer", 
    description="Converts the raw simulation output into the final structured, human-readable response.", 
    system_prompt_override=EXPLAINER_SYSTEM_PROMPT
)
