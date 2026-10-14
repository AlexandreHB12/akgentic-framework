"""ChecklistTool — read and overwrite the Payroll Quality Assistant's own checklist.

The checklist lives on PayrollQAState (see state.py), not on this card's
config, so it can be replaced at runtime (e.g. "here's a new checklist, use
this instead") and the replacement persists for the rest of the agent's
lifetime — nothing about the tool call is remembered elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable

from akgentic.tool.core import TOOL_CALL, BaseToolParam, Channels, ToolCard, _resolve
from akgentic.tool.core.observer import ActorToolObserver


class SetChecklist(BaseToolParam):
    """Parameters for the set-checklist capability."""

    expose: set[Channels] = {TOOL_CALL}


class GetChecklist(BaseToolParam):
    """Parameters for the get-checklist capability."""

    expose: set[Channels] = {TOOL_CALL}


def _render(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


class ChecklistTool(ToolCard):
    """Lets the agent read and replace its own persisted validation checklist."""

    set_checklist: SetChecklist | bool = True
    get_checklist: GetChecklist | bool = True

    def get_tools(self) -> list[Callable]:
        tools: list[Callable] = []
        set_params = _resolve(self.set_checklist, SetChecklist)
        if set_params and TOOL_CALL in set_params.expose:
            tools.append(self._set_factory(set_params))
        get_params = _resolve(self.get_checklist, GetChecklist)
        if get_params and TOOL_CALL in get_params.expose:
            tools.append(self._get_factory(get_params))
        return tools

    def _set_factory(self, params: SetChecklist) -> Callable:
        observer: ActorToolObserver = self._observer  # type: ignore[assignment]

        def set_checklist(items: list[str]) -> str:
            """Replace the current validation checklist with a new one.

            The new checklist fully replaces the old one — it is not merged —
            and persists for the rest of this agent's lifetime, until
            overwritten again by another call.

            Args:
                items: The new checklist, one check per item.

            Returns:
                A confirmation string listing the new checklist.
            """
            observer.state.checklist = list(items)  # type: ignore[attr-defined]
            return f"Checklist updated ({len(items)} items):\n{_render(items)}"

        set_checklist.__doc__ = params.format_docstring(set_checklist.__doc__)
        return set_checklist

    def _get_factory(self, params: GetChecklist) -> Callable:
        observer: ActorToolObserver = self._observer  # type: ignore[assignment]

        def get_checklist() -> str:
            """Return the validation checklist currently in effect.

            Call this before validating a timesheet, so checks run against
            whatever checklist is currently active (the default 3 checks,
            or a replacement set earlier via set_checklist).

            Returns:
                The current checklist, one numbered item per line.
            """
            items: list[str] = observer.state.checklist  # type: ignore[attr-defined]
            return _render(items)

        get_checklist.__doc__ = params.format_docstring(get_checklist.__doc__)
        return get_checklist
