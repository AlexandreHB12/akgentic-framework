"""MemoryTool — a small persistent, file-backed memory for an agent.

One memory per line in a plain text file — deliberately simple: no
concurrency control, no structured schema, just what was asked for (list,
add, forget one, forget all). Memory numbers are derived from line
position each time the file is read, not stored, so they always match
whatever list_memories most recently showed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from akgentic.tool.core import TOOL_CALL, BaseToolParam, Channels, ToolCard, _resolve
from akgentic.tool.errors import RetriableError


class ListMemories(BaseToolParam):
    """Parameters for the list-memories capability."""

    expose: set[Channels] = {TOOL_CALL}


class Remember(BaseToolParam):
    """Parameters for the remember (store-a-memory) capability."""

    expose: set[Channels] = {TOOL_CALL}


class Forget(BaseToolParam):
    """Parameters for the forget-one-memory capability."""

    expose: set[Channels] = {TOOL_CALL}


class ForgetAll(BaseToolParam):
    """Parameters for the forget-all-memories capability."""

    expose: set[Channels] = {TOOL_CALL}


class MemoryTool(ToolCard):
    """A small persistent memory: one line of text per memory, in a plain file.

    file_path is created (with its parent directory) on first write if it
    doesn't already exist yet.
    """

    file_path: str = "data/memory/team_coordinator_memories.txt"
    list_memories: ListMemories | bool = True
    remember: Remember | bool = True
    forget: Forget | bool = True
    forget_all: ForgetAll | bool = True

    def get_tools(self) -> list[Callable]:
        tools: list[Callable] = []
        list_params = _resolve(self.list_memories, ListMemories)
        if list_params and TOOL_CALL in list_params.expose:
            tools.append(self._list_factory(list_params))
        remember_params = _resolve(self.remember, Remember)
        if remember_params and TOOL_CALL in remember_params.expose:
            tools.append(self._remember_factory(remember_params))
        forget_params = _resolve(self.forget, Forget)
        if forget_params and TOOL_CALL in forget_params.expose:
            tools.append(self._forget_factory(forget_params))
        forget_all_params = _resolve(self.forget_all, ForgetAll)
        if forget_all_params and TOOL_CALL in forget_all_params.expose:
            tools.append(self._forget_all_factory(forget_all_params))
        return tools

    def _read_lines(self) -> list[str]:
        path = Path(self.file_path)
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_lines(self, lines: list[str]) -> None:
        path = Path(self.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines)
        path.write_text(f"{content}\n" if content else "", encoding="utf-8")

    def _list_factory(self, params: ListMemories) -> Callable:
        def list_memories() -> str:
            """List every stored memory, numbered for reference by forget.

            Returns:
                Each memory as "N. <text>" on its own line, or a message
                saying there are none yet.
            """
            lines = self._read_lines()
            if not lines:
                return "No memories stored yet."
            return "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))

        list_memories.__doc__ = params.format_docstring(list_memories.__doc__)
        return list_memories

    def _remember_factory(self, params: Remember) -> Callable:
        def remember(memory: str) -> str:
            """Store a new memory as one more line in the memory file.

            Args:
                memory: The text to remember. Internal newlines/extra
                    whitespace are collapsed to single spaces, since each
                    memory is exactly one line in the file.

            Returns:
                A confirmation string including the memory's new number.

            Raises:
                RetriableError: If the memory text is empty.
            """
            text = " ".join(memory.split())
            if not text:
                raise RetriableError("Cannot store an empty memory.")
            lines = self._read_lines()
            lines.append(text)
            self._write_lines(lines)
            return f"Remembered as #{len(lines)}: {text}"

        remember.__doc__ = params.format_docstring(remember.__doc__)
        return remember

    def _forget_factory(self, params: Forget) -> Callable:
        def forget(number: int) -> str:
            """Erase one memory by its number, as shown by list_memories.

            Args:
                number: The 1-based memory number to erase.

            Returns:
                A confirmation string naming the memory that was erased.

            Raises:
                RetriableError: If there's no memory with that number —
                    call list_memories first to see valid numbers.
            """
            lines = self._read_lines()
            if number < 1 or number > len(lines):
                raise RetriableError(
                    f"No memory numbered {number} — there "
                    f"{'is' if len(lines) == 1 else 'are'} only {len(lines)} stored. "
                    f"Call list_memories first."
                )
            removed = lines.pop(number - 1)
            self._write_lines(lines)
            return f"Forgot #{number}: {removed}"

        forget.__doc__ = params.format_docstring(forget.__doc__)
        return forget

    def _forget_all_factory(self, params: ForgetAll) -> Callable:
        def forget_all() -> str:
            """Erase every stored memory.

            Returns:
                A confirmation string with how many memories were erased.
            """
            count = len(self._read_lines())
            self._write_lines([])
            if count:
                return f"Forgot all {count} memories."
            return "There were no memories to forget."

        forget_all.__doc__ = params.format_docstring(forget_all.__doc__)
        return forget_all
