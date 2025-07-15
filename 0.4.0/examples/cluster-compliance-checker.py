#!/usr/bin/env python3
"""
Cluster Compliance Checker for Biotope Projects

This script helps cluster administrators verify that biotope projects
are using appropriate validation patterns for their requirements.

Usage:
    python cluster-compliance-checker.py [options]

Examples:
    # Check all projects in a directory
    python cluster-compliance-checker.py --scan-dir /cluster/projects

    # Check specific project
    python cluster-compliance-checker.py --project /path/to/project

    # Generate compliance report
    python cluster-compliance-checker.py --scan-dir /cluster/projects --report compliance_report.txt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import yaml


def find_biotope_projects(directory: Path) -> List[Path]:
    """Find all biotope projects in a directory tree."""
    projects = []
    
    for item in directory.rglob(".biotope"):
        if item.is_dir() and (item / "config" / "biotope.yaml").exists():
            projects.append(item.parent)
    
    return projects


def get_project_validation_info(project_path: Path) -> Optional[Dict]:
    """Get validation information for a biotope project."""
    try:
        config_path = project_path / ".biotope" / "config" / "biotope.yaml"
        if not config_path.exists():
            return None
        
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        
        validation_config = config.get("annotation_validation", {})
        
        # Get validation pattern
        pattern = validation_config.get("validation_pattern", "default")
        
        # Check for remote validation
        remote_config = validation_config.get("remote_config", {})
        if remote_config and remote_config.get("url"):
            url = remote_config.get("url", "")
            if "cluster" in url.lower() or "hpc" in url.lower():
                pattern = f"cluster-{pattern}"
            elif "storage" in url.lower() or "archive" in url.lower():
                pattern = f"storage-{pattern}"
        
        info = {
            "project_path": str(project_path),
            "validation_pattern": pattern,
            "enabled": validation_config.get("enabled", True),
            "required_fields": validation_config.get("minimum_required_fields", []),
            "remote_configured": bool(remote_config and remote_config.get("url")),
            "remote_url": remote_config.get("url") if remote_config else None,
            "compliance_status": "unknown"
        }
        
        # Determine compliance status
        if "cluster" in pattern.lower():
            info["compliance_status"] = "cluster_compliant"
        elif "storage" in pattern.lower():
            info["compliance_status"] = "storage_compliant"
        elif pattern == "default":
            info["compliance_status"] = "default_pattern"
        else:
            info["compliance_status"] = "custom_pattern"
        
        return info
        
    except Exception as e:
        return {
            "project_path": str(project_path),
            "error": str(e),
            "compliance_status": "error"
        }


def check_compliance(project_info: Dict, requirements: Dict) -> Dict:
    """Check if a project meets compliance requirements."""
    result = {
        "project_path": project_info["project_path"],
        "compliant": False,
        "issues": [],
        "warnings": []
    }
    
    # Check if validation is enabled
    if not project_info.get("enabled", True):
        result["issues"].append("Validation is disabled")
    
    # Check validation pattern
    pattern = project_info.get("validation_pattern", "default")
    required_pattern = requirements.get("required_pattern")
    
    if required_pattern and pattern != required_pattern:
        result["issues"].append(f"Wrong validation pattern: {pattern} (required: {required_pattern})")
    
    # Check required fields
    required_fields = requirements.get("required_fields", [])
    project_fields = project_info.get("required_fields", [])
    
    missing_fields = set(required_fields) - set(project_fields)
    if missing_fields:
        result["issues"].append(f"Missing required fields: {', '.join(missing_fields)}")
    
    # Check remote validation requirement
    if requirements.get("require_remote_validation", False):
        if not project_info.get("remote_configured", False):
            result["issues"].append("Remote validation not configured")
    
    # Determine overall compliance
    result["compliant"] = len(result["issues"]) == 0
    
    return result


def print_compliance_report(projects: List[Dict], requirements: Dict, output_file: Optional[str] = None):
    """Print a compliance report."""
    if output_file:
        output = open(output_file, 'w')
    else:
        output = sys.stdout
    
    try:
        output.write("=" * 80 + "\n")
        output.write("BIOTOPE CLUSTER COMPLIANCE REPORT\n")
        output.write("=" * 80 + "\n\n")
        
        # Summary
        total_projects = len(projects)
        compliant_projects = sum(1 for p in projects if p.get("compliance_status") in ["cluster_compliant", "storage_compliant"])
        default_patterns = sum(1 for p in projects if p.get("compliance_status") == "default_pattern")
        errors = sum(1 for p in projects if p.get("compliance_status") == "error")
        
        output.write(f"SUMMARY:\n")
        output.write(f"  Total projects: {total_projects}\n")
        output.write(f"  Compliant projects: {compliant_projects}\n")
        output.write(f"  Using default pattern: {default_patterns}\n")
        output.write(f"  Errors: {errors}\n")
        output.write(f"  Compliance rate: {compliant_projects/total_projects*100:.1f}%\n\n")
        
        # Detailed report
        output.write("DETAILED REPORT:\n")
        output.write("-" * 80 + "\n")
        
        for project in projects:
            output.write(f"\nProject: {project['project_path']}\n")
            output.write(f"  Pattern: {project.get('validation_pattern', 'unknown')}\n")
            output.write(f"  Status: {project.get('compliance_status', 'unknown')}\n")
            
            if "error" in project:
                output.write(f"  Error: {project['error']}\n")
                continue
            
            if project.get("remote_configured"):
                output.write(f"  Remote validation: {project.get('remote_url')}\n")
            
            required_fields = project.get("required_fields", [])
            if required_fields:
                output.write(f"  Required fields: {', '.join(required_fields)}\n")
            
            # Compliance check
            compliance = check_compliance(project, requirements)
            if compliance["compliant"]:
                output.write(f"  ✅ COMPLIANT\n")
            else:
                output.write(f"  ❌ NON-COMPLIANT\n")
                for issue in compliance["issues"]:
                    output.write(f"    - {issue}\n")
        
        output.write("\n" + "=" * 80 + "\n")
        output.write("RECOMMENDATIONS:\n")
        
        if default_patterns > 0:
            output.write(f"- {default_patterns} projects are using default validation pattern\n")
            output.write("  Consider configuring cluster-specific validation for these projects\n")
        
        if errors > 0:
            output.write(f"- {errors} projects have configuration errors\n")
            output.write("  Review these projects and fix configuration issues\n")
        
        if compliant_projects < total_projects:
            output.write(f"- {total_projects - compliant_projects} projects are non-compliant\n")
            output.write("  Contact project owners to update validation configuration\n")
        
    finally:
        if output_file:
            output.close()


def main():
    parser = argparse.ArgumentParser(description="Check biotope project compliance")
    parser.add_argument("--scan-dir", help="Directory to scan for biotope projects")
    parser.add_argument("--project", help="Specific project path to check")
    parser.add_argument("--report", help="Output file for compliance report")
    parser.add_argument("--requirements", help="JSON file with compliance requirements")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    # Default requirements
    requirements = {
        "required_pattern": "cluster-strict",
        "required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
        "require_remote_validation": True
    }
    
    # Load custom requirements if provided
    if args.requirements:
        with open(args.requirements) as f:
            requirements.update(json.load(f))
    
    # Find projects to check
    projects = []
    
    if args.project:
        project_path = Path(args.project)
        if (project_path / ".biotope" / "config" / "biotope.yaml").exists():
            projects = [project_path]
        else:
            print(f"Error: {args.project} is not a valid biotope project")
            sys.exit(1)
    
    elif args.scan_dir:
        scan_dir = Path(args.scan_dir)
        if not scan_dir.exists():
            print(f"Error: Directory {args.scan_dir} does not exist")
            sys.exit(1)
        
        print(f"Scanning {args.scan_dir} for biotope projects...")
        projects = find_biotope_projects(scan_dir)
        print(f"Found {len(projects)} biotope projects")
    
    else:
        print("Error: Must specify either --scan-dir or --project")
        sys.exit(1)
    
    # Get validation info for each project
    project_info = []
    for project_path in projects:
        info = get_project_validation_info(project_path)
        if info:
            project_info.append(info)
    
    # Output results
    if args.json:
        print(json.dumps(project_info, indent=2))
    else:
        print_compliance_report(project_info, requirements, args.report)
        
        if not args.report:
            print(f"\nChecked {len(project_info)} projects")
            compliant = sum(1 for p in project_info if p.get("compliance_status") in ["cluster_compliant", "storage_compliant"])
            print(f"Compliant: {compliant}/{len(project_info)} ({compliant/len(project_info)*100:.1f}%)")


if __name__ == "__main__":
    main() 