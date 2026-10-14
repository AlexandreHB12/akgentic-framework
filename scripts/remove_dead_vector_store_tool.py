"""Remove references to the now-deleted VectorStoreTool card across the catalog.

akgentic-tool epic 49 (commit 4b92152) deleted VectorStoreTool outright and
moved vector-store capability onto a `vector_store: VectorStoreParam | bool`
field that PlanningTool and KnowledgeGraphTool already carry (defaulting to
True) — so no separate tool attachment is needed any more. This script:

1. Deletes every `tool/id_vector_store.yaml` entry (the model_type it names,
   akgentic.tool.vector_store.VectorStoreTool, no longer exists).
2. Removes the corresponding `- __ref__: id_vector_store` /
   `- __ref__: global.id_vector_store` line from every agent that referenced
   it — those agents already carry id_planning/id_knowledge_graph, which keep
   working with vector-store search on by default.

Usage:
    python3 scripts/remove_dead_vector_store_tool.py
"""

from __future__ import annotations

from pathlib import Path

CATALOG_DIR = Path(__file__).parent.parent / "data" / "catalog"

REF_LINES = {
    "    - __ref__: id_vector_store\n",
    "    - __ref__: global.id_vector_store\n",
}


def main() -> None:
    removed_tools = 0
    for tool_file in CATALOG_DIR.glob("*/tool/id_vector_store.yaml"):
        tool_file.unlink()
        print(f"deleted {tool_file}")
        removed_tools += 1

    edited_agents = 0
    for agent_file in CATALOG_DIR.glob("*/agent/*.yaml"):
        lines = agent_file.read_text(encoding="utf-8").splitlines(keepends=True)
        filtered = [line for line in lines if line not in REF_LINES]
        if len(filtered) != len(lines):
            agent_file.write_text("".join(filtered), encoding="utf-8")
            print(f"edited {agent_file}")
            edited_agents += 1

    print(f"\nDeleted {removed_tools} tool entries, edited {edited_agents} agent entries.")


if __name__ == "__main__":
    main()
