# Biotope paper 1 — Where does human expertise matter when agents build biomedical knowledge graphs?

Status: paper and experiment plan, 7 September 2026. No proposed finding below is an established result. The early Biotope comparisons are development evidence only.

## The question

**Can a biomedical researcher use an agent to build and continually revise a useful knowledge graph without a knowledge-engineering specialist? If so, what must the researcher make explicit for that to work?**

A biomedical researcher knows the scientific problem. A knowledge-engineering specialist knows how to represent it through entities, relations, identifiers, mappings, and queries. One person can have both kinds of expertise; the experiment must distinguish their contributions.

**Working hypothesis:** Biotope's purpose elicitation can capture enough of the consequential scientific choices that agents can perform construction and revision with little additional specialist intervention. The benefit should appear in completed research tasks, including tasks introduced after the first graph is built.

We fail to support this hypothesis if acceptable performance depends on specialists repeatedly rewriting requirements or repairing the implementation. If an ordinary capable agent performs equally well, the evidence supports agent-assisted work but does not establish a benefit from Biotope's workflow.

## What the reader should learn

Agent construction from an existing expert schema and curated competency questions can conceal substantial human work. The scientific opportunity is to determine how much of that work a researcher–agent conversation can supply, and where specialist knowledge remains necessary.

The informative result would locate the difference:

| Possible result | Interpretation |
|---|---|
| Researcher + Biotope approaches the specialist-assisted reference, including after revisions | Specialist involvement can be reduced for the tested tasks and users. |
| Specialist corrections to the purpose record close the performance gap | The unresolved work lies in eliciting and formalizing requirements. |
| Specialists still improve outcomes after both workflows receive identical requirements | Important expertise remains in implementation or diagnosis. |
| Ordinary agent interaction performs as well as Biotope | Structured purpose elicitation has no demonstrated additional benefit in this setting. |

These are competing explanations to test. An average improvement alone would leave them unresolved.

Recent work already covers interactive ontology scoping ([OntoScope, IUI 2026](https://kclpure.kcl.ac.uk/portal/en/publications/ontoscope-using-a-divergent-convergent-interaction-framework-to-s/)), task-driven iterative graph and query-function construction ([OaK, August 2026 preprint](https://arxiv.org/html/2608.22974v1)), and the proposal that LLMs can help domain experts formulate requirements ([Zhao, 2025](https://link.springer.com/chapter/10.1007/978-3-031-99554-5_40)). Their existence rules out claiming that elicitation or iteration itself is new.

Human review also needs evidence. In [OE-Assist, 2025](https://arxiv.org/html/2507.14552), a study with 19 knowledge engineers found that correct LLM suggestions helped and incorrect suggestions harmed ontology evaluation; the overall accuracy improvement was not significant. Our proposed contribution is evidence about the placement of expertise across a complete biomedical workflow. Its novelty still requires a final targeted check before submission.

## The research episode

The unit of evaluation is a short investigation, not a single graph build:

```text
scientific aim → clarification and data inspection → first representation and answer
                         ↑                                      |
                         └──── new question, source, or correction┘
```

Each episode has an initial task and two or three meaningful revisions. Agents may ask questions, inspect sources, extend or prune a graph, rebuild it, or use a simpler representation. An incomplete first attempt is acceptable if the workflow recognizes the limitation and resolves it before the answer is accepted. Record which representation was used: success with tables counts toward research-task completion, but not as evidence of successful graph construction.

The study uses bounded deliverables within real research projects: an eligibility decision, a harmonized metadata table, a comparison of measured expression changes, or an evidence-backed revision of a shortlist. It does not require a universal score for whether an open research question has been “fully answered.”

## The available testbeds

### 1. INTRAC: controlled construction and revision

**Available:** heterogeneous differential-expression tables for atrial fibrillation, thrombosis, human and mouse myocardial infarction, and sepsis; study metadata; a many-to-many human–mouse ortholog mapping; and 16 competency questions (CQs, questions the representation should support).

**Readiness:** the strongest starting point for executable reference answers. However, the current CQs are development material. All 16 rows list LLM authors, including ten labelled `clinician`; human validation cannot be inferred from that label. Some expected answers require correction before reuse:

- “Changes the most” is answered by sorting adjusted p-values rather than effect sizes in CQ 0011.
- CQ 0018 treats a non-significant measured effect as unanswerable. The estimate can be reported with its uncertainty and significance status.
- CQ 0023 equates loss of significance with return to baseline. Its set counts do not establish biological recovery.
- CQ 0024 labels a cross-study set difference “clot-specific.” Study, tissue, assay, and reporting differences prevent that interpretation without further evidence.

The local Kaiser and Hill tables contain only significant results; Hill has just 15 rows according to the dataset notes. An absent row alone cannot distinguish an untested gene from a tested result omitted by filtering. Require the tested-gene universe or upstream evidence before making that distinction. Non-significance does not establish absence of an effect.

**Proposed episodes:**

| Initial task | Later change | What is checked |
|---|---|---|
| Report AF-versus-sinus-rhythm effects within one specified cohort and cell type | Add another AF study with different tissue and cell labels | Preserve study and tissue distinctions; report qualified agreement without silently pooling incompatible contrasts. |
| Compare significant human MI and thrombosis gene sets under explicit rules | Add sepsis, then obtain fuller results for a previously filtered study | Update counts and missingness explanations; distinguish newly available evidence from a biological change. |
| Describe human–mouse expression-direction agreement | Change the ortholog policy from all supported pairs to one-to-one pairs | Recompute from the declared policy, trace changed results, and preserve the original analysis version. |
| Compare mouse macrophage effects at two time points | Refine “persistent” to a specified measurable criterion | Implement the revised criterion and avoid treating significance patterns as proof of a time-course mechanism. |

**Public-data extension:** first investigate fuller author-supplied results for Hill and Kaiser. This improves interpretability without immediately introducing a new disease. Hill's [published study](https://pubmed.ncbi.nlm.nih.gov/39562555/) provides the starting reference; local notes identify SCP2489 and Kaiser's Zenodo source. Full unfiltered tables have not been verified as downloadable. If they require reanalysis, a domain expert must specify that analysis separately.

For a new source, screen [Chaffin et al., 2022, dilated and hypertrophic cardiomyopathy](https://www.nature.com/articles/s41586-022-04817-8), with processed data reported at SCP1303. It adds a different disease and anatomical context, making it useful for a revision test rather than a direct AF replication claim. Confirm effect tables, contrast definitions, cohort overlap, and access before admitting it.

Select the extension using declared scientific and accessibility criteria before comparing systems. No new data have been downloaded for this plan.

### 2. Daria: purpose-dependent dataset selection and harmonization

**Available:** the study inventory, an August scoping conversation, September CODEX/PhenoCycler screening criteria and candidate reports, plus local raw-file folders for four GEO series. The raw folders span other technologies; they are not evidence that the CODEX screening candidates are loaded.

**Scientific deliverable:** identify datasets usable for a specified metastasis-benchmark purpose, locate the required files, and produce reviewable study, technical, and metadata-field tables. Training a metastasis predictor and choosing segmentation pipelines are separate projects.

This case contains a documented refinement: the September criteria distinguish **metastatic tissue** from **primary tissue with known metastatic outcome**, and add a cohort-composition rule after the first screening. The records motivate an experiment; their existing recommendations are not independent ground truth.

**Proposed episodes:**

| Initial task | Later change | What is checked |
|---|---|---|
| Identify studies with sample-linked metastasis metadata | Specify primary-tumour outcome prediction versus primary/metastatic niche comparison | Update eligibility and retain the distinction between tissue sampled and patient outcome. For prediction, check whether outcome timing and follow-up support the intended target. |
| Map reported metastasis fields to a common summary | A new study separates distant spread, metastatic site, and lymph-node status | Preserve source meaning; obtain the researcher's mapping decision; do not collapse clinically different labels automatically. |
| Locate raw files needed for the agreed processing workflow | Discover that only processed objects are accessible | Correct eligibility, keep a reviewable reason, and identify what evidence or access would change the decision. |
| Summarize available samples and metadata | Add a study with several sections or cores per patient | Keep patient, sample, and imaging-unit counts distinct; recompute coverage using the agreed denominator. |

Use two tracks. A frozen packet of papers, supplements, repository records, and small metadata extracts tests representation and reasoning with equal source access. A later live acquisition test measures finding those sources. Report the outcomes separately to distinguish source discovery from modelling.

### 3. Aybüke's HIV immune atlas: prospective transfer

**Available:** a dataset-scouting workbook and detailed criteria. No expression corpus is loaded in the supplied directory. The workbook includes search-log and excluded entries, so its row count is not the number of usable datasets. References in the criteria to other project files do not establish that those files are present here.

**First deliverable:** an evidence-backed selection and integration plan for a small set of deposits. Build a metadata representation first; expression-level analyses depend on acquisition and validation.

Useful revisions follow the project's own distinctions:

- Shift from studying all immune cells in people with HIV to identifying HIV-infected cells. Reassess whether the deposit supports cell-level infection calls.
- Add a non-HIV inflammatory reference. Replace HIV-specific requirements with the appropriate condition, donor, treatment, and control requirements.
- Discover that a paper reports a capability absent from its public deposit. Update the answer and acquisition plan.
- Add in-vitro or ex-vivo material. Preserve model system, stimulation, and the different meanings of an HIV-negative cell.

This is the best prospective test because it is less shaped by the existing Biotope benchmark. The researcher should introduce genuine new needs after the first deliverable. One project owner can support a case study; a broad claim about ordinary researchers requires additional users.

## The comparisons

Use a small ladder of workflows rather than “expert graph versus agent graph” alone.

| Arm | Who does the work? | Purpose of the comparison |
|---|---|---|
| **A. Ordinary agent** | Biomedical researcher with a capable coding agent, ordinary conversation, source inspection, and iterative analysis | Establish what current agent use already achieves. |
| **B. Biotope** | The same kind of researcher and model, with Biotope's explicit purpose-and-CQ workflow | Measure the benefit of the complete Biotope workflow over A. |
| **C. Specialist-reviewed requirements** | B, with a knowledge engineer allowed to revise the requirements and mapping decisions in prose, but not implement them | Measure how much specialist contribution can be supplied through an explicit record. |
| **D. Specialist-assisted implementation** | The same approved requirements as C, with a knowledge engineer also allowed to inspect and repair implementation | Measure the residual contribution of specialist implementation and diagnosis. |

A and B are the practical comparison. C and D are diagnostic interventions. D is a contemporary specialist-assisted reference; historical expert graphs provide context, not an automatic gold standard or a reliable estimate of human time.

All arms can iterate and obtain scientific clarification. Use the same model version, source access, compute limit, and base tools where applicable. A can construct its own graph, use SQL or tables, and maintain provenance. Do not handicap it by withholding normal capabilities.

B minus A measures the whole workflow, not grilling alone. To isolate elicitation, replay the purpose records produced by ordinary conversation and Biotope into fresh copies of the same Biotope builder. Preserve substantive content and source references; exclude final answers and evaluator material. This tests the usefulness of the elicited record, not every effect of live interaction.

For C versus D, fork from the same requirements and source snapshot. If the specialist discovers a new scientific assumption during implementation, preserve the original comparison and run an additional replay that supplies this assumption to C. This separates the overall value of specialist help from the remaining implementation advantage once both arms have the same information.

Researchers can learn from one workflow and carry that knowledge into the next. Use different matched tasks and counterbalance workflow order in live comparisons; do not count a second attempt at an already solved case as independent evidence. Record prior familiarity, recruit additional researchers where feasible, and use replay experiments for comparisons that require identical scientific input.

## What “grilling” means in the experiment

Pin the interaction protocol before the main study. The current repository's workflow asks about purpose and revisits mismatches; the paper needs a reproducible account of the treatment being tested.

The output is a short, revisable purpose record covering:

1. The research decision or comparison to support.
2. The population, tissue, unit of observation, and relevant source scope.
3. Inclusion, comparison, and aggregation rules that affect the answer.
4. What would count as a useful answer, including examples and CQs.
5. Known evidence limits and choices still requiring the researcher.
6. Which decisions changed after inspecting data, and why.

The agent can use examples from the data to explain a choice. It should stop when the current task has an actionable specification and revisit it when necessary. Neither question count nor agreement with a long questionnaire is the outcome.

## Experiments

### E1. Does the elicited purpose record enable useful work?

Start with INTRAC and Daria. Give the researcher a genuine broad aim and the agent access to the corresponding sources. Compare A and B on complete episodes. Run the record-replay comparison on a preselected subset to separate elicitation from construction machinery.

**Prediction:** if purpose elicitation is the main mechanism, Biotope's records should improve outcomes even when a fresh, identical builder implements them. Already explicit tasks provide a control: little additional benefit there would be compatible with the hypothesis.

**Failure condition:** improvements appear only in the live combined workflow, or disappear after matching available resources and source access. That would require a different explanation from better elicitation alone. Obtaining more relevant information through better questions is a legitimate mechanism, provided all arms had the same opportunity to obtain it.

### E2. Where does specialist help change the outcome?

Compare B, C, and D on task families selected before seeing system performance, retaining both successes and failures. Record specialist interventions as corrections to scientific requirements, representation choices, or technical execution.

**Prediction:** if consequential expertise can be made explicit, C should recover most of D's advantage. If B already approaches D, specialists add little under the tested conditions. If D materially exceeds C, inspect the specific repairs responsible.

For informative interventions, fork the preceding state and replay the correction with and without its substantive content, allowing equal additional agent time. This distinguishes a useful correction from simply giving the system another attempt. Demonstrate effects on fresh examples rather than treating an intervention log as causal proof.

This experiment supplies the paper's explanation. E1 alone would be primarily a workflow comparison.

### E3. Does the conclusion survive extension, correction, and pruning?

Continue the episodes with a new source, a changed scientific rule, and an appropriate removal or correction. For example, withdraw an incorrectly included cohort and check that its measurements and derived counts disappear while its exclusion remains documented. Reveal each event when it occurs; neither the initial schema nor the graph is frozen.

Evaluate the new task and an independent set of earlier checks. Some previous answers should change; others should remain valid. The reference specifies which and why. Measure successful repair, new errors, and whether changes are traceable to evidence or an approved decision.

**Prediction:** researcher + Biotope remains useful across revisions without specialist involvement growing into the dominant operational activity. This is a prediction about the full process, not first-build completeness.

### E4. Does the workflow transfer to the HIV atlas project?

After freezing the protocol, run A and B prospectively with Aybüke on a small, independently verified deposit subset. Use C/D assistance as logged rescue where needed. Keep those rescued results separate from unaided B performance.

Start with deposit eligibility and metadata integration. Add an expression-level question only after the required files are present. Record useful task completion, user effort, changes in scientific requirements, and unresolved disagreements. This establishes a transfer case, not population-wide effectiveness.

### Optional E5. Are several smaller graphs better than one evolving graph?

Sebastian's preference for multiple smaller graphs needs a separate comparison. Use the same data, task sequence, approved purpose records, model, and total budget. Compare one graph that can be revised and pruned with several task-specific graphs that can share verified mappings and provenance.

Let the single graph adapt fully. Let the smaller graphs reuse work. Measure new-task success, regressions, duplicated or conflicting mappings, and human correction time. Graph size is descriptive, not the success criterion.

Include this in the first paper only if it reveals a reproducible difference worth explaining. Equal performance would support flexibility of implementation, not superiority of small graphs.

## Measurement and independent evaluation

**Primary outcome:** successful completion of the episode's research deliverable under an independently specified acceptance rubric. Report performance at each stage and final episode success. A correct, justified statement that the available evidence cannot support an analysis can pass; refusing answerable work cannot.

Use executable checks for numerical results, joins, source identities, eligibility rules, and coverage. Use blinded domain review for whether the answer supports the stated scientific use and acknowledges material limitations. Keep individual criteria visible, including partial completion; do not hide them inside one LLM-judged quality score. Critical errors, such as counting cells as independent donors or asserting an unsupported biological conclusion, prevent full acceptance even if easy checks pass.

Separate requirements from the evaluator. Users and systems may see construction CQs, but not hidden expected answers. Keep historical run outputs, completed screening recommendations, and evaluator files outside agent workspaces; specialist requirements are supplied only in their designated arms. Evaluate additional examples and subsequent tasks from the same scientific use. Validate reference answers directly from sources and independent code, not from either competing graph. Experts may recognize several scientifically valid interpretations; record these before unblinding results and adjudicate unresolved cases explicitly.

**Human effort:** record biomedical-researcher minutes and knowledge-engineer minutes separately for elicitation, review, implementation, and repair. Include preparation of supplied specialist requirements. Report benchmark construction and outcome adjudication separately as research overhead. Also record agent cost and elapsed time. No historical “months versus minutes” estimate substitutes for these measurements.

Claims of comparable performance require a prospectively chosen acceptable-loss margin and uncertainty intervals. A non-significant difference does not establish equivalence. Compare success at matched budgets and show quality versus human effort; do not claim to have found a globally optimal tradeoff.

Group related questions, stages, and model repetitions within their episode and source family. Repeated runs quantify agent variability; they do not create new researchers or independent biological datasets. Show results by project and task family, with paired uncertainty estimates that respect this grouping.

## Figures and manuscript skeleton

| Figure | Content | Manuscript role |
|---|---|---|
| **F1** | One concrete Daria or INTRAC episode, its scientific choices, and the four workflow arms | Introduction and study design. Explain the problem in terms a biomedical reader can recognize. |
| **F2** | Research-task success for A–D, with human effort broken down by role | Results 1: establish capability and the amount of specialist dependence. |
| **F3** | Purpose-record replay and intervention results | Results 2: identify which information or specialist action changes outcomes. |
| **F4** | Success, legitimate answer changes, and regressions across extension and pruning | Results 3: test the conclusion as research needs evolve. |
| **F5** | Prospective HIV case, including limitations and any specialist rescue | Results 4: transfer to a new project. |

**F3 and F4 should carry the scientific contribution.** A software diagram and an aggregate agent-versus-expert score are insufficient on their own.

The abstract should state the uncertainty, the comparison, the observed outcome, and its scope. Leave the result sentence unwritten until results exist. Introduce Biotope in one short main-text methods section: purpose record, explicit mappings, reproducible construction, and revision history. Put command details, schema files, model settings, full CQs, and validation code in Methods or the supplement.

The Discussion should explain which expertise the evidence shows can be delegated, which remains necessary, and how changing goals affect that conclusion. Separate observed outcomes from the longer-term vision of temporary, purpose-specific graphs.

## Sequence and scope

| Stage | Work | Decision it enables |
|---|---|---|
| 0 | Audit INTRAC CQs and sources; verify Daria candidate evidence; select episode families and independent assessors | Can we measure useful outcomes credibly? |
| 1 | Pilot two INTRAC and two Daria episodes, each with revisions; run A–D with three agent repetitions | Are there interpretable differences, and is human participation feasible? This is up to 48 episode runs, not 48 independent scientific cases. |
| 2 | Freeze the protocol, models, acceptance rules, allowable performance loss, and study/source splits | Commit to what would support or refute the claim before the main run. |
| 3 | Run E1–E3 on new episode families and study sources; size the study from pilot variability and feasible human participation | Estimate effects and distinguish their causes. A planning target is 8–12 episodes per primary project; this is not a power calculation. |
| 4 | Replicate the decisive comparison on a second current model and run E4 prospectively | Assess sensitivity to model and project. |
| 5 | Run E5 only if capacity and pilot evidence justify it | Decide whether “multiple smaller graphs” belongs in this paper. |

The smallest coherent scientific version is E1–E3 on INTRAC and Daria, with validated outcomes and informative intervention evidence. HIV strengthens transfer but should not force a full atlas build. If the pilot supplies only a working-system demonstration, write a methods paper with that scope rather than claiming the stronger hypothesis has been established.

Keep outside this first study: novel metastasis prediction models, new HIV perturbation models, a universal metric of scientific usefulness, a universal graph-selection rule, and claims that an expert graph must answer every future question. Open Targets can be an additional construction-from-requirements check if a verified evaluation set is available; it is not a prerequisite for this plan.

Before the main run, the team must settle the acceptable task-performance loss, the available domain and knowledge-engineering participants, and the final public INTRAC extension. Freeze the exact Biotope protocol and software revision as well. The repository currently describes itself as pre-alpha.

## Local source map

The source inspection supports the readiness assessment above. It did not validate all biological results or the contents of every downloaded file.

- [Reference paper-plan structure](/Users/vlad/CoworkProjects/emergence/docs/plans/paper1_local_to_global.md).
- [Sebastian's concept](</Users/vlad/CoworkProjects/Helmholtz/grant-applications/biotope_general/keeping semantic authority human.md>), [Biotope repository](/Users/vlad/Projects/virtual-human-dev/biotope), and [current operator workflow](/Users/vlad/Projects/virtual-human-dev/biotope/skills/biotope-croissant/SKILL.md).
- Daria: [scoping conversation](/Users/vlad/Projects/virtual-human-dev/daria_mvp/data/context/2026-08-04_align_daria-romanovskaia_schema-agent-mvp-scoping_summary.md), [project foundation](/Users/vlad/Projects/virtual-human-dev/daria_mvp/data/context/project-foundation.md), [input inventory](/Users/vlad/Projects/virtual-human-dev/daria_mvp/data/context/darias_input.xlsx), [revised screening criteria](/Users/vlad/Projects/virtual-human-dev/daria_mvp/data/codex_screening_2026-09-03/criteria.md), and [screening workbook](/Users/vlad/Projects/virtual-human-dev/daria_mvp/data/codex_screening_2026-09-03/datasheet.xlsx).
- INTRAC: [dataset notes](/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/DATASET_NOTES.txt), [purpose](/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/purpose.txt), [current CQs](/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/competency_questions.csv), and [source files](/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/workspace/raw).
- HIV atlas: [criteria](/Users/vlad/Projects/virtual-human-dev/usecases/aybueke_hiv_immune_atlas/criteria.md) and [scouting workbook](/Users/vlad/Projects/virtual-human-dev/usecases/aybueke_hiv_immune_atlas/datasheet-2.xlsx).
