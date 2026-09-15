#!/usr/bin/env python3
"""Compare local Biotope configuration with a project's stated requirements.

This example reads configuration only. It does not fetch remote policies or
validate dataset contents. See the annotation policy administration notes.
"""

import argparse
import json
from pathlib import Path

import yaml


DEFAULT_REQUIREMENTS = {
    "required_pattern": "cluster-strict",
    "required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
    "require_remote_validation": True,
}


def find_biotope_projects(directory: Path) -> list[Path]:
    """Find projects with local configuration, in path order."""
    return sorted({path.parent.parent for path in directory.rglob(".biotope/config.yaml") if path.is_file()})


def check_project(project: Path, requirements: dict) -> dict:
    """Compare a project's local settings with the supplied requirements."""
    result = {"project_path": str(project), "matches_requirements": False, "issues": []}
    try:
        config = yaml.safe_load((project / ".biotope/config.yaml").read_text()) or {}
        validation = config.get("annotation_validation", {})
        remote = validation.get("remote_config", {}) or {}
        fields = validation.get("minimum_required_fields", [])
        if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
            raise ValueError("minimum_required_fields must be a list of strings")
        pattern = validation.get("validation_pattern", "default")
        result.update(
            validation_pattern=pattern,
            enabled=validation.get("enabled", True),
            required_fields=fields,
            remote_url=remote.get("url"),
        )
        if not result["enabled"]:
            result["issues"].append("Annotation validation is disabled")
        required_pattern = requirements.get("required_pattern")
        if required_pattern and pattern != required_pattern:
            result["issues"].append(f"Pattern is {pattern!r}; expected {required_pattern!r}")
        missing = sorted(set(requirements.get("required_fields", [])) - set(fields))
        if missing:
            result["issues"].append(f"Required fields are not configured locally: {', '.join(missing)}")
        if requirements.get("require_remote_validation") and not remote.get("url"):
            result["issues"].append("Remote validation URL is not configured")
        result["matches_requirements"] = not result["issues"]
    except (OSError, yaml.YAMLError, AttributeError, TypeError, ValueError) as error:
        result["issues"].append(f"Cannot read configuration: {error}")
    return result


def make_report(projects: list[Path], requirements: dict) -> dict:
    """Create one report with summary counts derived from project results."""
    results = [check_project(project, requirements) for project in projects]
    matching = sum(result["matches_requirements"] for result in results)
    return {
        "schema_version": 1,
        "scope": "local_configuration",
        "requirements": requirements,
        "summary": {"projects": len(results), "matching": matching, "not_matching": len(results) - matching},
        "projects": results,
    }


def render_text(report: dict) -> str:
    """Render the configuration comparison as a text report."""
    summary = report["summary"]
    lines = [
        "Biotope local configuration report",
        "Dataset contents and remote policy responses were not checked.",
        f"Projects: {summary['projects']}; matching requirements: {summary['matching']}",
    ]
    if not report["projects"]:
        lines.append("No Biotope projects found.")
    for project in report["projects"]:
        state = "MATCH" if project["matches_requirements"] else "MISMATCH"
        lines.append(f"\n{project['project_path']}: {state}")
        lines.extend(f"  - {issue}" for issue in project["issues"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scan-dir", type=Path, help="Directory containing Biotope projects")
    selection.add_argument("--project", type=Path, help="One project to inspect")
    parser.add_argument("--requirements", type=Path, help="JSON file overriding the default requirements")
    parser.add_argument("--report", type=Path, help="Write the report to this file instead of stdout")
    parser.add_argument("--json", action="store_true", help="Emit a single JSON document")
    args = parser.parse_args()

    requirements = DEFAULT_REQUIREMENTS.copy()
    if args.requirements:
        try:
            overrides = json.loads(args.requirements.read_text())
            if not isinstance(overrides, dict):
                raise ValueError("requirements must be a JSON object")
            unknown = set(overrides) - set(DEFAULT_REQUIREMENTS)
            if unknown:
                raise ValueError(f"unsupported requirements: {', '.join(sorted(unknown))}")
            requirements.update(overrides)
            fields = requirements["required_fields"]
            if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
                raise ValueError("required_fields must be a list of strings")
            if not isinstance(requirements["require_remote_validation"], bool):
                raise ValueError("require_remote_validation must be a boolean")
            if requirements["required_pattern"] is not None and not isinstance(requirements["required_pattern"], str):
                raise ValueError("required_pattern must be a string or null")
        except (OSError, ValueError, TypeError) as error:
            parser.error(str(error))

    if args.project:
        projects = [args.project.resolve()]
    else:
        if not args.scan_dir.is_dir():
            parser.error(f"Not a directory: {args.scan_dir}")
        projects = find_biotope_projects(args.scan_dir.resolve())
    report = make_report(projects, requirements)
    output = json.dumps(report, indent=2) + "\n" if args.json else render_text(report)
    if args.report:
        args.report.write_text(output)
    else:
        print(output, end="")
    return 0 if projects and report["summary"]["not_matching"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
