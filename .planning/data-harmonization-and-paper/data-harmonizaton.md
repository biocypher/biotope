# Daria — spatial multi-omics data and metadata curation 08-2026

> Project foundation created with Agentic Automation Canvas v2 (2.0-draft.5).
> This is a discovery brief for a first MVP, not implementation approval or production readiness.

## 1. Work today

### What is this project about?

Build a standardized spatial multi-omics resource for a metastasis benchmark. This collaboration covers the parsing block before any bulk download: determine whether useful metadata and raw data exist, find the exact raw-data download link, extract technical details, harmonize sample-level metadata into Daria's v0 schema, and keep every decision reviewable. Preprocessing is a separate later stream informed by Daria's preprocessing benchmark.

### Who actually does this work today?

Daria owns the schema project, scientific workflow and review decisions. The team currently curates papers and metadata and searches repositories manually; students previously piloted preprocessing, and Nikita has used AI for dataset discovery. Vlad will build the first filtering pass and reproduce the student reference work while Daria is on the other benchmark and then on vacation. The Lücken-lab benchmark team receives the result. Missing: long-term production maintainer and infrastructure/access owner.

### What happened in the most recent real case?

The team assembled a large table of pre-identified studies, priority tiers and sample counts; roughly half the selection was curated manually. Daria tested Claude against her schema and curated table, and Nikita found 42 additional datasets in about two hours. In normal curation, people still search papers, many supplementary tables and repository pages by hand to determine whether metadata and raw data exist and where the exact downloadable raw files are. The student pilot covered preprocessing, not clinical-metadata standardization.

### How large is the problem?

The starting corpus is roughly 100 public datasets, but Daria expects only 10–20 to satisfy the metastasis use case. A study's metadata may be spread across about 10 supplementary tables. Individual samples are tens of GB and datasets can reach TB scale, so incorrect inclusion creates material download, storage and compute cost. Missing: human hours per study, current error/rework rate and the minimum dataset count required per modality.

## 2. Change

### What should happen differently in the next real case?

For each pre-identified study, establish in order: whether metadata exists; whether it contains useful fields; whether raw data is accessible and the exact raw-data download link; and how the metadata maps into shared fields. Produce a study table retaining accepted and rejected studies with reasons, a technical table with original preprocessing details, and a schema-field table with provenance and uncertainty. Daria then reviews the results before any download; one sample may be checked only when metadata is hidden in the data object.

### Why is this change important enough to act on now?

Metadata parsing and harmonization is the largest public-atlas bottleneck and the gate before costly downloads. If reliable, the method could benefit many Atlas projects and support a methodological publication. Schema is Daria's second priority: her other benchmark has a hard resource deadline on 12 August, she is occupied through August and then on vacation, while autumn is the peak period for schema work. Schema is nominally due by year-end; the next benchmarking-track application date still needs confirmation.

### What trade-offs are acceptable, and what must not be sacrificed?

A messy German Excel v0, a narrow first pass and extensive human review are acceptable; the schema need not be cleaned or final before testing. Do not sacrifice the two hard inclusion checks—metadata available and raw data available—field-level provenance, reviewable mappings, or the rejected-study record. Biological relevance sets priority rather than automatic exclusion. Daria retains scientific decisions. Later preprocessing may trade about 2% signal-to-noise for speed, but chosen steps must be uniform across datasets.

## 3. Solutions

### What have you already tried, and what happened?

Manual curation and a student pilot established the workflow, but the students only covered preprocessing and never reached clinical-metadata standardization. Claude Code has been useful for schema-guided paper checks, dataset discovery and template-based loader/config generation. Daria already has a family of preprocessing skills and defined metrics, but those depend on the Open Problems platform and are not directly reusable for schema. Automated visual/output checking is still weak.

### Why do you believe a better solution is possible now?

The team already has a curated study list with tiers and sample counts, a large target schema, metadata tables, existing data loaders, pipeline templates and a preprocessing-skill family. Daria is fluent with Claude Code and wants an interpretable process; prior tests showed useful extraction and config generation. LaminDB is being established for dataset tracking and sharing. Missing: measured metadata accuracy, net time saving and performance on difficult supplements, inaccessible data and conflicting terminology.

### Which AI or agentic approaches do you want to try, and what do you expect each to improve?

Use Claude Code for an interpretable parsing agent that locates metadata and exact raw-data links, extracts technical preprocessing details, maps heterogeneous fields and resolutions into shared fields, retains source lineage, and flags ambiguity. Biotope is a candidate for the mapping step. Later agents may construct loaders and help inspect plots, but Daria—not the agent—chooses the scientific workflow and preprocessing steps.

### What solutions already exist, and which are actually credible here?

Start from the existing curated list, metadata tables and v0 schema in Claude Code. Build the parsing block first: presence and relevance checks, exact raw-link discovery, study/technical/schema-field tables, traceable mapping and human review. Use Biotope where helpful for field mapping. Reuse the team's existing data loaders and emerging LaminDB later; do not rebuild them. Bulk download, workflow orchestration and preprocessing automation are outside this first collaboration deliverable.

## 4. Development reality

### What data would be used in development and in real operation?

Inputs are the pre-identified paper list with priority and sample counts, papers and supplementary tables, repository records, Daria's large German Excel v0 schema, metadata tables and standards. Metadata spans dataset, sample and cell levels; the first pass focuses on study/sample information and technical methods. The target should preserve the union of shared fields, not only a fixed required subset; examples include sex, age bands and metastasis status. Some metadata may exist only in an AnnData .obs object. Missing: final starting subset, schema version, source access rights, licenses and sensitive-data assessment.

### Where would it run, and what must it connect to?

The first parsing pass runs in Claude Code against accessible papers, supplements, the curated list, v0 schema and public repository pages; it does not require bulk cluster storage. It must return exact raw-data links and reviewable tables. The team already has data loaders and is establishing LaminDB for tracking and sharing; later loaders can download batches into LaminDB, followed by batch QC and a Nextflow or Snakemake preprocessing pipeline. Missing for the first test: shared repository/workspace, document storage and any required repository credentials.

### Which technical, legal, security, or organizational constraint could block this?

Metadata can be absent, split across inconsistent supplements, encoded at different resolutions or hidden inside a shared data object; raw files may be missing, inaccessible or available only on request. Exact ages may be withheld for privacy and appear only as bands. The v0 schema is messy and German, but usable for testing. Keep blocked studies visible: highly relevant ones go to human follow-up with authors; lower-priority ones may be rejected with a recorded reason. Confirm paper/download rights, sensitive-data status, document access and repository credentials.

### Who will build, review, operate, and maintain it—and what time is actually committed?

Daria owns the scientific workflow, target fields and acceptance review. By the end of this week—she has time Thursday/Friday—she will send the metadata-process slide, tables and standard, dataset list, v0 schema, and student results or presentation. Vlad will build the first metadata-presence filtering pass and reproduce the student reference work while Daria is occupied through August and then on vacation. Work is async until September, with the next meeting in September. Missing: committed engineering capacity after September and long-term operations/maintenance ownership.

## 5. Value and evidence

### What must change around the technology before the benefit can appear—and who owns each change?

Daria must provide the v0 schema, source tables, dataset list and process slide. Vlad must turn the agreed parsing sequence into a reviewable first pass. The team must encode the two inclusion checks, priority tiers, table-pair outputs, shared-field mapping, provenance and rejected-study reasons; make papers and supplements accessible; and establish visual human review of sample counts, categories and availability calls. Long-term maintenance and access ownership must be assigned before scaling.

### What scientific value should this create?

A reusable, comparable spatial multi-omics resource for finding biological niches across datasets and developing metastasis-risk models, without confounding those patterns with incompatible processing or metadata semantics. Reliable metadata research and raw-source identification could also become a broadly useful Atlas-community method—and potentially a methodological publication—while the team's own balanced cohort later tests whether transcriptomic patterns and clinically translatable protein biomarkers generalize.

### Which metrics will track progress and decide whether the change is valuable?

Track: (1) share of studies for which metadata presence, useful fields, raw-data availability and an exact raw link are correctly established; (2) share of mapped values with source provenance and reviewer-confirmed semantics; (3) reviewer-confirmed correctness of inclusion, rejection and tier decisions; and (4) net Daria review time per study versus manual curation, including false leads and avoided downloads. Expect only 10–20 usable datasets, but baselines, numerical targets and the stop/reshape threshold still need agreement before the run.

## 6. MVP

### Which named user and workflow slice will the first MVP cover?

User: Daria as scientific curator. Start with the existing pre-identified study list and validate the parser on a small representative subset before the wider first filtering pass. For each study, inspect papers, supplements and repositories; determine metadata usefulness and raw-data accessibility; find the exact raw link; map metadata into the v0 shared-field schema; and produce study, technical and schema-field tables for review. Outside scope: bulk download, loader rebuilding, preprocessing, segmentation and production orchestration.

### What must that user be able to achieve in the MVP?

As Daria, I can see whether each study has useful metadata and accessible raw data, with the exact download link, so that I avoid costly dead-end downloads.

As Daria, I can review sample metadata mapped to shared fields with source lineage and uncertainty, so that I can accept or correct harmonization.

As Daria, I can inspect original preprocessing details and all accepted or rejected studies with reasons, so that I can follow up on biologically important blocked cases.

As Daria, I can review sample counts and category visualizations before scaling, so that the agent's filtering remains under scientific control.

### How will users and developers work together during the MVP?

Daria will provide the process slide, metadata tables/standard, dataset list, v0 schema and student material by the end of the week. Vlad will implement the first filtering pass and reference test while she is on the other benchmark and vacation; Daria will review visualized study and metadata results rather than monitor daily. Collaboration is async until September, with the next meeting then. Still to establish: shared repository, paper/test-data workspace, issue/decision log and the exact review handoff.

### What must be resolved before a first build or test can start?

1. Receive Daria's process slide, metadata tables/standard, dataset list, v0 schema and student material.
2. Select the small representative validation subset and the minimum dataset count per modality.
3. Turn the two inclusion criteria, priority tiers, study/technical/schema-field tables and shared-field mapping into a v0 output contract.
4. Establish the Claude Code repository/workspace and paper/supplement access.
5. Agree review views and acceptance targets for availability calls, mappings, provenance and net review time.
6. Confirm the September review date and what result permits a wider filtering pass.
7. Assign long-term maintenance and infrastructure/access ownership before moving to loaders and downloads.
