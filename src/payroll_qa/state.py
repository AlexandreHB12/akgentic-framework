"""AgentState extension carrying the Payroll Quality Assistant's checklist.

BaseAgent.on_start() hardcodes a plain AgentState, with no override hook —
so a custom persisted field requires a bespoke State subclass, swapped in
by PayrollQAAgent.on_start() right after the parent's setup has run.
"""

from __future__ import annotations

from pydantic import Field

from akgentic.agent.config import AgentState

DEFAULT_CHECKLIST: list[str] = [
    "Ensure that all employees worked less than 40 hours a week",
    "Ensure that the employees in the timesheet appear in the payroll data",
    "Ensure that all employees are adults",
]


class PayrollQAState(AgentState):
    """AgentState plus the currently-active validation checklist."""

    checklist: list[str] = Field(default_factory=lambda: list(DEFAULT_CHECKLIST))
