"""Sales/Marketing Agent (market and sales): Round 1 domain analysis. Thin wrapper over agents.specialist."""

from agents.base import AgentResult
from agents.specialist import run_specialist_analysis


def run_marketing_agent(pitch_text: str, moderator_opening: str = "") -> AgentResult:
    """Run the Sales/Marketing Agent (market and sales) on the full pitch with the specialist length budget."""
    return run_specialist_analysis("marketing", pitch_text, moderator_opening)
