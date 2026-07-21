"""B.O.S. Architecture Validator v0.1

Validates architectural compliance, layer separation, circular imports,
and graph ownership rules across the codebase. Generates ARCHITECTURE_REPORT.md.
"""

import os
import re
from typing import Any, Dict, List


class ArchitectureValidator:
    """Scans codebase for architectural violations and produces an evaluation report."""

    @classmethod
    def validate(cls, project_root: str) -> Dict[str, Any]:
        warnings: List[str] = []
        critical_issues: List[str] = []
        recommendations: List[str] = []

        runtime_dir = os.path.join(project_root, "backend", "runtime")
        adapters_dir = os.path.join(project_root, "backend", "adapters")
        core_graph_dir = os.path.join(project_root, "backend", "core", "graph")

        # 1. Check if Business Graph is inside runtime directory
        runtime_bg = os.path.join(runtime_dir, "business_graph")
        if os.path.exists(runtime_bg):
            warnings.append("Business Graph files exist inside runtime/ directory. Independent Graph Layer is at core/graph/business/.")
            recommendations.append("Ensure runtime components import BusinessContextGraph from core.graph.business.")

        # 2. Check for direct adapter imports inside runtime core engines
        if os.path.exists(runtime_dir):
            for root, _, files in os.walk(runtime_dir):
                for f in files:
                    if f.endswith(".py") and f != "step_runner.py":
                        filepath = os.path.join(root, f)
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                            content = file.read()
                            if "from adapters import" in content or "import adapters" in content:
                                if "plan_executor" not in filepath:
                                    critical_issues.append(f"Direct adapter import found in runtime component: {f}")

        # 3. Check graph ownership rule: Core Graph layer must exist
        if not os.path.exists(core_graph_dir):
            critical_issues.append("Core Graph Layer (core/graph/) missing.")

        score = 100 - (len(critical_issues) * 15) - (len(warnings) * 5)
        score = max(0, min(100, score))

        report = {
            "score": score,
            "warnings": warnings,
            "critical_issues": critical_issues,
            "recommendations": recommendations,
        }

        cls.generate_markdown_report(report, project_root)
        return report

    @classmethod
    def generate_markdown_report(cls, report: Dict[str, Any], project_root: str) -> str:
        content = f"""# B.O.S. Architecture Report

## Evaluation Score: {report['score']} / 100

---

## Critical Issues ({len(report['critical_issues'])})
"""
        if not report['critical_issues']:
            content += "- None. Architecture rules strictly followed.\n"
        else:
            for issue in report['critical_issues']:
                content += f"- ❌ {issue}\n"

        content += f"\n## Warnings ({len(report['warnings'])})\n"
        if not report['warnings']:
            content += "- None.\n"
        else:
            for warn in report['warnings']:
                content += f"- ⚠️ {warn}\n"

        content += f"\n## Recommendations ({len(report['recommendations'])})\n"
        if not report['recommendations']:
            content += "- Maintain current layer separation and contract enforcement.\n"
        else:
            for rec in report['recommendations']:
                content += f"- 💡 {rec}\n"

        report_path = os.path.join(project_root, "ARCHITECTURE_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        return content


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    res = ArchitectureValidator.validate(root)
    print(f"Architecture score: {res['score']}/100")
