"""PayrollQAAgent — a BaseAgent whose state also carries a validation checklist.

BaseAgent.on_start() builds the ReactAgent, tool factory and context updater
around a plain AgentState with no seam to inject extra fields. Rather than
duplicating that ~90-line method, this subclass runs it unmodified via
super().on_start() and then swaps self.state for a PayrollQAState carrying
the same backstory/tool_state plus the checklist — everything on_start()
already wired up (react agent, tools, context updater) keeps working, since
PayrollQAState is an AgentState.
"""

from __future__ import annotations

from akgentic.agent import BaseAgent

from .state import PayrollQAState


class PayrollQAAgent(BaseAgent):
    """BaseAgent whose state also persists a configurable validation checklist."""

    def on_start(self) -> None:
        super().on_start()
        self.state = PayrollQAState(
            backstory=self.state.backstory,
            tool_state=self.state.tool_state,
        ).observer(self)
