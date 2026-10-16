"""CFO Agent (finance): Round 1 domain analysis. Thin wrapper over agents.specialist."""

from agents.base import AgentResult
from agents.specialist import run_specialist_analysis


def run_cfo_agent(pitch_text: str, moderator_opening: str = "") -> AgentResult:
    """Run the CFO Agent (finance) on the full pitch with the specialist length budget."""
    return run_specialist_analysis("cfo", pitch_text, moderator_opening)
