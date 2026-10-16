"""Experimental conditions."""

from workflows.multi_workflow import run_multi_workflow
from workflows.single_workflow import run_single_workflow

WORKFLOWS = {"single": run_single_workflow, "multi": run_multi_workflow}

__all__ = ["WORKFLOWS", "run_multi_workflow", "run_single_workflow"]
