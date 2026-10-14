"""Regenerate support-team catalog tool entries from the fake-data CSVs.

Reads CSV files from FAKE_DATA_DIR and embeds their content into WorkspaceTool
resources, split across three data-backed tools: Salesforce data (Customer
Engagement Assistant), payroll data (Payroll Assistant), and general
knowledge-base data (Knowledge Assistant). Rerun after refreshing the
fake-data source at ~/Desktop/Work/akgent_onboarding/fake-data.

Usage:
    uv run python scripts/seed_support_team_data.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

FAKE_DATA_DIR = Path.home() / "Desktop/Work/akgent_onboarding/fake-data"
CATALOG_TOOL_DIR = Path(__file__).parent.parent / "data/catalog/support-team/tool"


class LiteralStr(str):
    """Marker so the YAML dumper renders this string as a literal block scalar."""


def _literal_str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(LiteralStr, _literal_str_representer)


def _resource(file_name: str) -> dict[str, Any]:
    text = (FAKE_DATA_DIR / file_name).read_text(encoding="utf-8")
    return {"file_name": file_name, "file_type": "text", "content": LiteralStr(text)}


def _build_tool(
    entry_id: str,
    description: str,
    workspace_id: str,
    instructions: str,
    files: list[str],
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "kind": "tool",
        "namespace": "support-team",
        "user_id": "anonymous",
        "model_type": "akgentic.tool.workspace.WorkspaceTool",
        "description": description,
        "payload": {
            "workspace_id": workspace_id,
            "read_only": True,
            "workspace_view": False,
            "expand_media_refs": False,
            "workspace_read": {"instructions": instructions},
            "resources": [_resource(f) for f in files],
        },
    }


TOOLS: list[dict[str, Any]] = [
    _build_tool(
        "id_salesforce_data",
        "Five curated Salesforce cases, each requiring payroll data or sector/CCT knowledge",
        "support-team-salesforce",
        (
            "A small, demo-sized case list — deliberately not the full Salesforce export "
            "(see salesforce_cases.csv / salesforce_cases_payroll_linked.csv in the "
            "fake-data folder for that). Each of the 5 cases names a real employeeNumber "
            "and cites real figures from the payroll data, and none of them can be "
            "answered from this file alone: a tax-increase case needs the Payroll "
            "Assistant to compare payslips, an indexation/mobility case needs the "
            "Knowledge Assistant for the sector's collective agreement, a vacation-days "
            "case needs payroll days-taken data, and a meal/eco-voucher case needs the "
            "granted amounts per period. See generate_demo_cases.py for how each figure "
            "was pulled from the source CSVs."
        ),
        [
            "salesforce_cases_demo.csv",
        ],
    ),
    _build_tool(
        "id_payroll_calendar",
        "Dummy payroll calendar — when each client's payroll computation is due",
        "support-team-payroll-calendar",
        (
            "One row per (employer, payrollPeriod): periodEndDate, computationDueDate, "
            "status (completed / completed_with_errors / failed for periods already run, "
            "matching los21_payroll_run_status.csv exactly for 2026-07 — or upcoming / "
            "scheduled for periods not yet run) and notes, e.g. an employer's "
            "timesheet-cutoff day from los21_employer_instructions.csv. Compare "
            "computationDueDate against the current date (given in your own system "
            "prompt) to say how soon a client's payroll is due, or whether it's overdue."
        ),
        [
            "los21_payroll_calendar.csv",
        ],
    ),
    _build_tool(
        "id_calculated_payroll_data",
        "Payroll contracts, calculated salary data, wage codes and employer instructions",
        "support-team-payroll",
        (
            "los21_contracts_employees.csv lists one row per contract (people with two "
            "contracts have contractCount > employeeCount). "
            "los21_calculated_data_summary.csv has one row per active employee per "
            "payment period (gross/taxable/net/social_deductions/fiscal_deductions/"
            "net_attribution/cost/total_cost). los21_calculated_data_lines.csv is the "
            "same data flattened to one row per line item. "
            "los21_employer_instructions.csv carries employer instructions and "
            "validation messages. los21_joint_committees.csv lists joint committees per "
            "dossier. wage_codes.csv documents every wage code per dossier, including "
            "employer-specific overrides (isClientSpecific=true)."
        ),
        [
            "los21_contracts_employees.csv",
            "los21_calculated_data_summary.csv",
            "los21_calculated_data_lines.csv",
            "los21_employer_instructions.csv",
            "los21_joint_committees.csv",
            "wage_codes.csv",
        ],
    ),
    _build_tool(
        "id_payroll_run_tool",
        "Payroll run status and raw engine-reported errors for the current (2026-07) run",
        "support-team-payroll-runs",
        (
            "los21_payroll_run_status.csv has one row per (dossier, period) payroll run: "
            "status (completed / completed_with_errors / failed), employees processed, "
            "employees with errors. los21_payroll_run_errors.csv has one row per raw "
            "engine-reported error within a run: errorCode, errorCategory, severity, "
            "fieldOrCode and an uninterpreted engineMessage — every employeeNumber/"
            "dossierNumber here also appears in los21_contracts_employees.csv. The "
            "engine states the error as-is; it does not explain why it occurred or how "
            "to fix it — that interpretation is this tool's consumer's job."
        ),
        [
            "los21_payroll_run_status.csv",
            "los21_payroll_run_errors.csv",
        ],
    ),
    _build_tool(
        "id_troubleshooter_data",
        (
            "Payroll run status/errors, contract and calculated payroll data, and "
            "knowledge-base reference data, combined into one workspace for the "
            "Troubleshooter"
        ),
        "support-team-troubleshooter",
        (
            "Combines three data sources the Troubleshooter needs together in one "
            "workspace (a single agent can only carry one WorkspaceTool, since each "
            "one exposes an identically-named workspace_read tool — see "
            "id_payroll_run_tool / id_calculated_payroll_data / id_knowledge_base for "
            "the same files split by role instead). "
            "los21_payroll_run_status.csv has one row per (dossier, period) payroll "
            "run: status (completed / completed_with_errors / failed), employees "
            "processed, employees with errors. los21_payroll_run_errors.csv has one "
            "row per raw engine-reported error within a run: errorCode, "
            "errorCategory, severity, fieldOrCode and an uninterpreted "
            "engineMessage — the engine states the error as-is; it does not explain "
            "why it occurred or how to fix it, that's this tool's consumer's job. "
            "los21_contracts_employees.csv lists one row per contract (people with "
            "two contracts have contractCount > employeeCount). "
            "los21_calculated_data_summary.csv has one row per active employee per "
            "payment period (gross/taxable/net/social_deductions/fiscal_deductions/"
            "net_attribution/cost/total_cost); los21_calculated_data_lines.csv is "
            "the same data flattened to one row per line item. "
            "los21_employer_instructions.csv carries employer instructions and "
            "validation messages. los21_joint_committees.csv lists joint committees "
            "per dossier. wage_codes.csv documents every wage code per dossier, "
            "including employer-specific overrides (isClientSpecific=true). "
            "digifaq_entries.csv, infoweb_documents.csv, payroll_wiki_pages.csv and "
            "los21_wiki_pages.csv are internal FAQ/wiki articles; "
            "external_websites.csv covers RVA/ONEM, FOD WASO/SPF Emploi, RSZ/ONSS "
            "and NAR/CNT reference pages; ten_commandments.csv is the termination "
            "checklist (NL/FR); belgian_holidays.csv lists 2026 public/school/bank "
            "holidays."
        ),
        [
            "los21_payroll_run_status.csv",
            "los21_payroll_run_errors.csv",
            "los21_contracts_employees.csv",
            "los21_calculated_data_summary.csv",
            "los21_calculated_data_lines.csv",
            "los21_employer_instructions.csv",
            "los21_joint_committees.csv",
            "wage_codes.csv",
            "digifaq_entries.csv",
            "infoweb_documents.csv",
            "payroll_wiki_pages.csv",
            "los21_wiki_pages.csv",
            "external_websites.csv",
            "ten_commandments.csv",
            "belgian_holidays.csv",
        ],
    ),
    _build_tool(
        "id_knowledge_base",
        "FAQ, wiki, external reference, product package and calendar/math reference data",
        "support-team-knowledge",
        (
            "digifaq_entries.csv and infoweb_documents.csv are internal FAQ/"
            "knowledge-base articles. payroll_wiki_pages.csv and los21_wiki_pages.csv "
            "are internal wiki search results. external_websites.csv covers RVA/ONEM, "
            "FOD WASO/SPF Emploi, RSZ/ONSS and NAR/CNT reference pages. "
            "ella_queries.csv/ella_sources.csv/ella_model_docs.csv are the ELLA payroll "
            "knowledge assistant's own Q&A history and source catalog. "
            "ten_commandments.csv is the termination checklist (NL/FR). "
            "belgian_holidays.csv lists 2026 public/school/bank holidays. "
            "math_expressions.csv has verified payroll arithmetic examples. "
            "nbo_packages.csv describes the commercial packages."
        ),
        [
            "digifaq_entries.csv",
            "infoweb_documents.csv",
            "payroll_wiki_pages.csv",
            "los21_wiki_pages.csv",
            "external_websites.csv",
            "ella_queries.csv",
            "ella_sources.csv",
            "ella_model_docs.csv",
            "ten_commandments.csv",
            "belgian_holidays.csv",
            "math_expressions.csv",
            "nbo_packages.csv",
        ],
    ),
]


def main() -> None:
    CATALOG_TOOL_DIR.mkdir(parents=True, exist_ok=True)
    for tool in TOOLS:
        out_path = CATALOG_TOOL_DIR / f"{tool['id']}.yaml"
        out_path.write_text(
            yaml.dump(tool, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
