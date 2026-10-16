"""CTO Agent (technology): Round 1 domain analysis. Thin wrapper over agents.specialist."""

from agents.base import AgentResult
from agents.specialist import run_specialist_analysis


def run_cto_agent(pitch_text: str, moderator_opening: str = "") -> AgentResult:
    """Run the CTO Agent (technology) on the full pitch with the specialist length budget."""
    return run_specialist_analysis("cto", pitch_text, moderator_opening)
