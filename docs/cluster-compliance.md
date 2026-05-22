# Cluster Compliance with Biotope

Biotope supports robust cluster compliance workflows for institutional and collaborative environments. This page explains how to enforce, check, and monitor metadata validation policies across multiple projects, especially in shared or high-performance computing (HPC) clusters.

______________________________________________________________________

## Overview

Cluster compliance ensures that all biotope projects on a cluster adhere to organization-wide metadata requirements. This is critical for:

- **Data integrity and reproducibility**
- **Institutional policy enforcement**
- **Automated project onboarding and review**
- **Long-term storage and archival**

Biotope enables compliance through:

- **Validation patterns**: Project-level configuration for required metadata fields
- **Remote validation**: Centralized, cluster-wide validation policies
- **Compliance checking**: Automated tools for admins to scan and report on project compliance

______________________________________________________________________

## Admin Workflow: Enforcing Compliance

1. **Define Cluster Requirements**
   - Create a requirements file (e.g., `cluster-requirements.json`) with required fields and patterns.
   - Example:
     ```json
     {
       "cluster_name": "Example HPC Cluster",
       "required_pattern": "cluster-strict",
       "required_fields": [
         "name", "description", "creator", "dateCreated", "distribution", "license", "project_id"
       ],
       "require_remote_validation": true
     }
     ```
1. **Set Up Remote Validation**
   - Deploy a remote validation server (see [examples/remote-validation-server.py](examples/remote-validation-server.py)).
   - Provide users with the remote validation URL.
1. **Automate Compliance Checking**
   - Use the [cluster compliance checker](examples/cluster-compliance-checker.py) to scan all projects:
     ```bash
     python cluster-compliance-checker.py --scan-dir /cluster/projects --requirements /etc/biotope/cluster-requirements.json --report /var/log/biotope/compliance-$(date +%Y%m%d).txt
     ```
   - Integrate with cron or CI/CD for regular monitoring.
1. **Monitor and Alert**
   - Track compliance rates and alert administrators if compliance drops below a threshold.

______________________________________________________________________

## User Workflow: Ensuring Project Compliance

1. **Initialize your project**
   ```bash
   biotope init
   ```
1. **Set the cluster validation pattern**
   ```bash
   biotope config set-validation-pattern --pattern cluster-strict
   ```
1. **Configure remote validation**
   ```bash
   biotope config set-remote-validation --url https://cluster.example.com/validation/cluster-strict
   ```
1. **Check your configuration**
   ```bash
   biotope config show-validation-pattern
   biotope config show-validation
   ```
1. **Annotate and validate your data**
   - Use `biotope annotate` and `biotope status` to ensure all required fields are present.

______________________________________________________________________

## Example Compliance Report

```
================================================================================
BIOTOPE CLUSTER COMPLIANCE REPORT
================================================================================

SUMMARY:
  Total projects: 25
  Compliant projects: 18
  Using default pattern: 5
  Errors: 2
  Compliance rate: 72.0%

DETAILED REPORT:
--------------------------------------------------------------------------------

Project: /cluster/projects/user1/experiment
  Pattern: cluster-strict
  Status: cluster_compliant
  Remote validation: https://cluster.example.com/validation/cluster-strict
  Required fields: name, description, creator, dateCreated, distribution, license, project_id
  **✅ COMPLIANT**

Project: /cluster/projects/user2/data
  Pattern: default
  Status: default_pattern
  Required fields: name, description, creator, dateCreated, distribution
  **❌ NON-COMPLIANT**
    - Wrong validation pattern: default (required: cluster-strict)
    - Missing required fields: license, project_id
    - Remote validation not configured

================================================================================
RECOMMENDATIONS:
- 5 projects are using default validation pattern
  Consider configuring cluster-specific validation for these projects
- 2 projects have configuration errors
  Review these projects and fix configuration issues
- 7 projects are non-compliant
  Contact project owners to update validation configuration
```

______________________________________________________________________

## Integration with Cluster Management

- **Automated Checks**: Integrate compliance checking into cron jobs or CI/CD pipelines.
- **User Onboarding**: Provide setup instructions for new users (see above).
- **Monitoring**: Use scripts to monitor compliance rates and send alerts.

______________________________________________________________________

## Best Practices

### For Cluster Administrators

- Define clear requirements and validation patterns
- Automate compliance checking and reporting
- Provide clear documentation and onboarding for users
- Monitor compliance trends and support users

### For Users

- Set the correct validation pattern for your project
- Use remote validation if required
- Regularly check your compliance status
- Seek help from administrators if needed

### For Developers

- Extend validation patterns for new use cases
- Test compliance workflows with different configurations
- Document new patterns and requirements

______________________________________________________________________

## Agentic + baker annotation on a cluster

Metadata management is the *primary* biotope use case on shared clusters — most
projects there don't need the Croissant → BioCypher KG build. What they do need
is a reliable way to get every dataset annotated to the cluster's required
pattern. Two pieces help:

### Where to put the project root

Cluster filesystems usually have no metadata of their own. A biotope project
should live at the level a single experiment / dataset / user-collaboration
already occupies — typically `/cluster/projects/<user>/<experiment>/`. Rules
of thumb:

- **One `.biotope/` per logical unit of work**, not one for an entire user
  home. The validation pattern, remote-validation URL, and required-fields
  list are per-project.
- **Project root must contain its data.** `biotope add` rejects paths outside
  the project tree (and rejects symlinks pointing out of it) so a project
  stays self-describing for the compliance checker and downstream collaborators.
- For shared lab directories, prefer one `biotope init` per dataset directory
  over a single mega-project at the lab root — it keeps validation patterns
  and remote-validation policies aligned with how the data is actually owned.

### Which files to annotate, and how

`biotope add <path>` runs **croissant-baker** recursively under `<path>` and
classifies each discovered file:

- **Baker-supported formats** (CSV, Parquet, TSV, JSON, FASTA, …) get a
  populated `recordSet`/`fileObject` and are marked `biotope:status: processed` — they are ready for downstream use.
- **Unsupported formats** (PDFs, opaque binaries, remote URLs, …) get a
  minimal manifest marked `biotope:status: raw`. These are the files that
  need agentic or manual follow-up before they count as fully annotated.

`biotope queue` (or `biotope queue --json` for batch tooling) lists every
tracked file by status. Use it as the worklist for annotation backlogs.

### Agents as cluster annotation workers

Agents drive the same CLI a human admin would. A typical cluster annotation
loop:

```bash
# 1. Find everything still raw across all projects.
for proj in /cluster/projects/*/; do
  (cd "$proj" && biotope queue --json) | jq '.raw[]'
done

# 2. For each raw item: derive a baker-annotatable artifact (extract tables
#    from a PDF, fetch a remote URL into the project, …) and re-add it,
#    pointing back at the original via --derived-from.
biotope add data/extracted/report.csv --derived-from data/raw/report.pdf

# 3. The new artifact bakes cleanly and lands as 'processed'. The raw input
#    is still tracked for provenance.
```

`biotope/templates/AGENTS.md` (shipped into every project by `biotope init`)
already encodes this workflow as the agent contract — point your agent at the
project root and it will pick up the queue and the rules. Note that the KG
sections (`biotope map`, `biotope build`) are optional; an agent operating in
a pure-metadata cluster project can stop after every dataset reaches
`processed` and the compliance checker reports green.

## References and further reading

- [Remote validation server example](examples/remote-validation-server.py)
- [Cluster compliance checker](examples/cluster-compliance-checker.py)
- [Project context](project-context.md) — `.biotope/` layout and config files
- [Architecture](architecture.md) — where baker, queue, and mark fit in the data flow
