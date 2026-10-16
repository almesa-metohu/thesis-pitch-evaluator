"""CEO Agent (strategy): Round 1 domain analysis. Thin wrapper over agents.specialist."""

from agents.base import AgentResult
from agents.specialist import run_specialist_analysis


def run_ceo_agent(pitch_text: str, moderator_opening: str = "") -> AgentResult:
    """Run the CEO Agent (strategy) on the full pitch with the specialist length budget."""
    return run_specialist_analysis("ceo", pitch_text, moderator_opening)
