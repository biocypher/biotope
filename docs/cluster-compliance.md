# Cluster Compliance with Biotope

Biotope supports robust cluster compliance workflows for institutional and collaborative environments. This page explains how to enforce, check, and monitor metadata validation policies across multiple projects, especially in shared or high-performance computing (HPC) clusters.

---

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

---

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
2. **Set Up Remote Validation**
   - Deploy a remote validation server (see [examples/remote-validation-server.py](examples/remote-validation-server.py)).
   - Provide users with the remote validation URL.
3. **Automate Compliance Checking**
   - Use the [cluster compliance checker](examples/cluster-compliance-checker.py) to scan all projects:
     ```bash
     python cluster-compliance-checker.py --scan-dir /cluster/projects --requirements /etc/biotope/cluster-requirements.json --report /var/log/biotope/compliance-$(date +%Y%m%d).txt
     ```
   - Integrate with cron or CI/CD for regular monitoring.
4. **Monitor and Alert**
   - Track compliance rates and alert administrators if compliance drops below a threshold.

---

## User Workflow: Ensuring Project Compliance

1. **Initialize your project**
   ```bash
   biotope init
   ```
2. **Set the cluster validation pattern**
   ```bash
   biotope config set-validation-pattern --pattern cluster-strict
   ```
3. **Configure remote validation**
   ```bash
   biotope config set-remote-validation --url https://cluster.example.com/validation/cluster-strict
   ```
4. **Check your configuration**
   ```bash
   biotope config show-validation-pattern
   biotope config show-validation
   ```
5. **Annotate and validate your data**
   - Use `biotope annotate` and `biotope status` to ensure all required fields are present.

---

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

---

## Integration with Cluster Management

- **Automated Checks**: Integrate compliance checking into cron jobs or CI/CD pipelines.
- **User Onboarding**: Provide setup instructions for new users (see above).
- **Monitoring**: Use scripts to monitor compliance rates and send alerts.

---

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

---

## References and Further Reading

- [Remote Validation Server Example](examples/remote-validation-server.py)
- [Cluster Compliance Checker Script](examples/cluster-compliance-checker.py)
- [Validation Patterns and Examples](https://github.com/biocypher/biotope/tree/main/docs/examples)
- [Git Integration for Users](git-integration.md)
- [Developer & Admin Guide: Annotation Validation](git-integration-dev.md) 