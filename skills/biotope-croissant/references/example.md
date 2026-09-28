# Worked example: two studies and a methods note

A complete small project, file by file. It passes `biotope graph check` with strict Pyright and builds. Use it for the shape of each file and the contracts between them. Its scientific choices follow this skill's defaults; your sources and purpose decide yours.

## Contents

- The inputs and the commands
- Shared terms
- Schemas
- Locating a described file
- Loaders, tables and documents
- Topology
- Alignment
- Mappings
- The stage sequence and the pipeline
- What the check and build report
- Strict typing patterns

## The inputs and the commands

```text
data/study_a.csv   gene,ensembl_id,log2fc,padj              (padj is empty for untested genes)
data/study_b.csv   Gene,gene_id,logFC,FDR,cluster           (gene_id is empty for one symbol)
data/methods.txt   who was compared with whom, per study
```

```bash
biotope init . --no-prompt
biotope graph scaffold
biotope map --purpose "Find genes whose expression changes in atrial fibrillation in both studies" \
  --entity "gene" --entity "differential expression result" --relation "result reports gene"
biotope add data --json
biotope source generate .biotope/datasets/data.jsonld --out graph/sources
```

Baker describes both tables, as RecordSets `study_a` and `study_b` over FileObjects `file_0` and `file_1`. It cannot parse `methods.txt`, so `biotope add` appends FileObject `file_9608b3c3` for it. Generation creates `graph/sources/data/{study_a,study_b,methods_txt}/`, each holding `schema.py`, `__init__.py` (the `SOURCE` registration, kept as generated) and a placeholder `loader.py`. All three are selected: `graph/sources/__init__.py` stays as scaffolded, with `EXCLUDED_SOURCES = {}`.

## Shared terms

Both tables report a symbol, an accession, a fold change and an adjusted p-value, and the graph reads each pair as one meaning. Declaring the terms makes that equivalence visible and checked: `run.json` lists, for each term, the source field of every schema bound to it.

```python
# graph/standardization.py
GENE_SYMBOL = Term("gene_symbol", "Gene symbol as the source reports it; not resolved to an accession.")
GENE_ACCESSION = Term("gene_accession", "Ensembl gene accession, as the source supplies it.")
LOG2_FOLD_CHANGE = Term(
    "log2_fold_change", "Log2 fold change between the source's case and reference groups, as reported."
)
ADJUSTED_P_VALUE = Term("adjusted_p_value", "Multiple-testing adjusted p-value, as the source reports it.")

TERMS: tuple[Term, ...] = (GENE_SYMBOL, GENE_ACCESSION, LOG2_FOLD_CHANGE, ADJUSTED_P_VALUE)
```

`study_b`'s `cluster` has no counterpart in `study_a`, so it stays a preserved field without a term.

## Schemas

The generated schemas start with every field nullable and named as in the file. Tightened and bound, with the attribute named after its term:

```python
# graph/sources/data/study_a/schema.py (header comment omitted)
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biotope.graph import source_field

from ....standardization import ADJUSTED_P_VALUE, GENE_ACCESSION, GENE_SYMBOL, LOG2_FOLD_CHANGE


@dataclass(frozen=True, kw_only=True)
class StudyA:
    __record_set__: ClassVar[str] = "study_a"
    __source_digest__: ClassVar[str] = "d88f42eff4d1…"  # the full revision, as generated
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    gene_symbol: str = source_field("gene", term=GENE_SYMBOL)
    gene_accession: str | None = source_field("ensembl_id", term=GENE_ACCESSION)
    log2_fold_change: float = source_field("log2fc", term=LOG2_FOLD_CHANGE)
    # Empty when the gene was filtered before testing (methods.txt, paragraph 2).
    adjusted_p_value: float | None = source_field("padj", term=ADJUSTED_P_VALUE)
```

```python
# graph/sources/data/study_b/schema.py: the fields only
    gene_symbol: str = source_field("Gene", term=GENE_SYMBOL)
    gene_accession: str | None = source_field("gene_id", term=GENE_ACCESSION)
    log2_fold_change: float = source_field("logFC", term=LOG2_FOLD_CHANGE)
    adjusted_p_value: float = source_field("FDR", term=ADJUSTED_P_VALUE)
    cluster: str  # binds study_b/cluster by its own name
```

A document's `Facts` schema gets the fields you transcribe:

```python
# graph/sources/data/methods_txt/schema.py: the fields added under the generated ClassVars
    study: str  # the record set the statement is about
    case_group: str
    reference_group: str
```

## Locating a described file

Evidence cites a file and a pinned version. Both come from the manifest's FileObject, so one helper beside the loaders serves every source of the manifest:

```python
# graph/sources/data/_files.py
def described_file(source: SourceContract, file_id: str) -> tuple[Path, str, str]:
    """Return the path, "sha256:<digest>" and project-relative name of one FileObject.

    Baker writes contentUrl relative to the directory it scanned (data/ for
    .biotope/datasets/data.jsonld); FileObjects that `biotope add` appends for files
    Baker cannot parse are relative to the project root. Changed content is refused.
    """
    manifest = cast(dict[str, Any], json.loads(source.metadata.read_text(encoding="utf-8")))
    entry = next(item for item in cast(list[dict[str, Any]], manifest["distribution"]) if item["@id"] == file_id)
    scanned = PROJECT_ROOT / source.metadata.resolve().relative_to(PROJECT_ROOT / ".biotope/datasets").with_suffix("")
    url = str(entry["contentUrl"])
    path = next((base / url for base in (scanned, PROJECT_ROOT) if (base / url).is_file()), scanned / url)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != entry["sha256"]:
        raise ValueError(f"{path}: content differs from the described sha256; review the manifest first")
    return path, "sha256:" + actual, path.relative_to(PROJECT_ROOT).as_posix()
```

Modules in a root, and directories without a `schema.py`, are helpers: inventory collection ignores them.

## Loaders, tables and documents

The generated loader keeps its two functions; only `_read` is written, and the placeholder line is deleted:

```python
# graph/sources/data/study_a/loader.py
def _optional(raw: str) -> str | None:
    return None if raw.strip().lower() in StudyA.__missing_values__ else raw


def _read(config: None) -> Iterator[SourceRecord[StudyA]]:
    """Yield one record per row; missing tokens become None, nothing is filtered."""
    path, version, artifact = described_file(SOURCE, "file_0")
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            padj = _optional(row["padj"])
            record = StudyA(
                gene_symbol=row["gene"],
                gene_accession=_optional(row["ensembl_id"]),
                log2_fold_change=float(row["log2fc"]),
                adjusted_p_value=None if padj is None else float(padj),
            )
            yield SourceRecord(record, (Evidence(artifact, version, StudyA.__record_set__, f"line {line}"),))


def load(context: RunContext) -> Iterator[SourceRecord[StudyA]]:
    yield from context.load(SOURCE, _read, None)
```

A document's loader returns the facts you transcribed after reading the file, each with the location it came from:

```python
# graph/sources/data/methods_txt/loader.py: _read; load() is as generated
TRANSCRIBED = (
    (Facts(study="study_a", case_group="atrial fibrillation (AF)", reference_group="sinus rhythm (SR)"), "paragraph 2"),
    (Facts(study="study_b", case_group="atrial fibrillation (AF)", reference_group="sinus rhythm (SR)"), "paragraph 3"),
)


def _read(config: None) -> Iterator[SourceRecord[Facts]]:
    _, version, artifact = described_file(SOURCE, Facts.__file_object__)
    for facts, location in TRANSCRIBED:
        yield SourceRecord(facts, (Evidence(artifact, version, Facts.__record_set__, location),))
```

## Topology

```python
# graph/topology/gene/__init__.py
GeneId = NewType("GeneId", str)


@dataclass(frozen=True)
class Gene:
    """A gene as the sources identify it; no identity is inferred from a matching symbol.

    `ensembl:<accession>` when a source supplied the accession, shared by every source
    that did. `symbol:<source>/<symbol>` when a source gave only a symbol: it stays
    local to that source, so one gene can appear under several ids.
    """

    schema_id: ClassVar[str] = "af:gene"
    id: GeneId
    symbols: list[str] = field(metadata={"description": "Every symbol a source reported for this identity, sorted."})
    accession: str | None = field(
        default=None, metadata={"description": "Ensembl gene accession a source supplied; None for a symbol-only node."}
    )
```

```python
# graph/topology/result/__init__.py
ResultId = NewType("ResultId", str)


@dataclass(frozen=True)
class Result:
    """One tested gene in one study; rows the study filtered before testing are excluded.

    Admission is not significance: filter adjusted_p_value to choose a threshold.
    """

    schema_id: ClassVar[str] = "af:result"
    id: ResultId
    study: str = field(metadata={"description": "The record set that reported the result: study_a or study_b."})
    log2_fold_change: float = field(
        metadata={"description": "Log2 fold change, case group over reference group, as the study reports it."}
    )
    adjusted_p_value: float = field(
        metadata={"description": "The study's multiple-testing adjusted p-value (study_a: Benjamini-Hochberg)."}
    )
    case_group: str = field(metadata={"description": "The group the fold change is for, from methods.txt."})
    reference_group: str = field(metadata={"description": "The group the fold change is against, from methods.txt."})


@dataclass(frozen=True)
class ResultReportsGene:
    """The result is about this gene, as the study named it; many results to one gene."""

    schema_id: ClassVar[str] = "af:result_reports_gene"
    source: ResultId
    target: GeneId
```

`graph/topology/__init__.py` registers them: `TOPOLOGY = Topology(nodes=(Gene, Result), edges=(ResultReportsGene,))`.

## Alignment

Every row contributes identity evidence before any row is admitted, and the result does not depend on read order. Two rows share a gene only when both supply the same accession; a matching symbol is not enough, so `PLN`, which `study_b` gives without an accession, stays `symbol:study_b/PLN`. Whether it may be merged is a question for the user, recorded in `graph/ASSUMPTIONS.md`.

```python
# graph/alignment/genes.py
@dataclass(frozen=True)
class GeneIdentity:
    """A resolved gene identity and every symbol reported for it."""

    gene_id: str
    accession: str | None
    symbols: tuple[str, ...]


def gene_key(row: StudyA | StudyB) -> str:
    if row.gene_accession:
        return f"ensembl:{row.gene_accession}"
    return f"symbol:{type(row).__record_set__}/{row.gene_symbol}"


def resolve_genes(rows: list[SourceRecord[StudyA] | SourceRecord[StudyB]]) -> dict[str, SourceRecord[GeneIdentity]]:
    symbols: dict[str, set[str]] = {}
    evidence: dict[str, set[Evidence]] = {}
    for row in rows:
        key = gene_key(row.value)
        symbols.setdefault(key, set()).add(row.value.gene_symbol)
        evidence.setdefault(key, set()).update(row.evidence)
    identities: dict[str, SourceRecord[GeneIdentity]] = {}
    for key in sorted(symbols):
        accession = key.removeprefix("ensembl:") if key.startswith("ensembl:") else None
        identity = GeneIdentity(gene_id=key, accession=accession, symbols=tuple(sorted(symbols[key])))
        identities[key] = SourceRecord(identity, tuple(sorted(evidence[key])))
    return identities
```

Because both schemas name their fields after the shared terms, `row.gene_accession` reads either study without a branch.

## Mappings

```python
# graph/mappings/result/__init__.py
def make_gene(identity: SourceRecord[GeneIdentity]) -> Iterator[Gene]:
    gene = identity.value
    yield Gene(id=GeneId(gene.gene_id), symbols=list(gene.symbols), accession=gene.accession)


def make_result(
    row: SourceRecord[StudyA | StudyB], gene: SourceRecord[GeneIdentity], facts: SourceRecord[Facts]
) -> Iterator[Result | ResultReportsGene]:
    """Both schemas bind the same terms, so one mapping reads either study's rows."""
    value = row.value
    if value.adjusted_p_value is None:
        raise ValueError(f"{row.evidence[0]}: compose excludes untested rows before this mapping")
    study = type(value).__record_set__
    # A natural key: a second row with the same key and other values fails the build.
    group = f"{value.cluster}/" if isinstance(value, StudyB) else ""
    result_id = ResultId(f"result:{study}/{group}{gene.value.gene_id}")
    yield Result(
        id=result_id,
        study=study,
        log2_fold_change=value.log2_fold_change,
        adjusted_p_value=value.adjusted_p_value,
        case_group=facts.value.case_group,
        reference_group=facts.value.reference_group,
    )
    yield ResultReportsGene(source=result_id, target=GeneId(gene.value.gene_id))


GENES = Mapping(name="af:gene", function=make_gene, requirements=("entity:gene",))
RESULTS = Mapping(
    name="af:result",
    function=make_result,
    requirements=("entity:differential expression result", "relation:result reports gene"),
    evidence=("Group labels come from methods.txt; values are kept as each study reports them.",),
)
```

`graph/mappings/__init__.py` registers them: `MAPPINGS: tuple[MappingEntry, ...] = (GENES, RESULTS)`.

## The stage sequence and the pipeline

```python
# graph/pipelines/compose.py
def run(context: RunContext) -> None:
    facts = {record.value.study: record for record in load_methods(context)}
    rows: list[SourceRecord[StudyA] | SourceRecord[StudyB]] = [*load_study_a(context), *load_study_b(context)]
    # Identity comes before admission: every row contributes evidence, admitted or not.
    genes = resolve_genes(rows)
    reported: set[str] = set()
    admitted = 0
    for row in rows:
        if row.value.adjusted_p_value is None:
            context.exclude("untested_gene", row.evidence)
            continue
        admitted += 1
        key = gene_key(row.value)
        reported.add(key)
        context.map(RESULTS, row, genes[key], facts[type(row.value).__record_set__])
    for key in sorted(reported):
        context.map(GENES, genes[key])
    context.record_audit(
        "results",
        inputs="every row of study_a and study_b",
        outputs="one Result and one ResultReportsGene per tested row; one Gene per identity they report",
        selection="Admit every row with an adjusted p-value; significance is a query filter.",
        counts={"rows": len(rows), "admitted": admitted, "genes": len(reported)},
    )
```

In `graph/pipelines/build_graph.py`, only these scaffolded fields change:

```python
    name="af-expression",
    scope=(
        "Every tested gene in study_a and study_b, one Result per row; rows filtered before testing are "
        "excluded. Genes keep the identity their source supplied; symbols are not merged into accessions."
    ),
    requirements={
        "entity:gene": "af:gene",
        "entity:differential expression result": "af:result",
        "relation:result reports gene": "af:result_reports_gene",
    },
    policies={"untested_gene": "A row without an adjusted p-value was filtered before testing (methods.txt)."},
```

## What the check and build report

- `biotope graph check --json`: state `checked`, no findings.
- `biotope graph build`: 4 genes, 6 results and 6 edges, and `Excluded 1: untested_gene`. `NPPA` and `MYH6` are one gene each, because both studies supply their accessions.
- `run.json`, `definitions.standardization`: `adjusted_p_value` is bound to `study_a/padj` and `study_b/FDR`, and so on for each term. `cluster` is listed as a preserved field.

## Strict typing patterns

The check runs Pyright in strict mode over the whole workspace. These patterns pass it:

- Annotate empty containers: `symbols: dict[str, set[str]] = {}`, and `field(default_factory=dict[str, set[str]])` in a dataclass.
- `json.loads` returns `Any`: `cast` it once, where the manifest is read.
- `SourceRecord` is covariant: a `list[SourceRecord[StudyA] | SourceRecord[StudyB]]` element passes to a parameter annotated `SourceRecord[StudyA | StudyB]`.
- Intermediate and source records may hold `str`, `int`, `float`, `bool`, `None`, a `NewType`, `list[...]`, `tuple[...]` or a dataclass; `graph check` rejects anything else. Graph properties are narrower: nullable scalars and lists of strings.
- A loader built on pandas meets untyped APIs. Keep them inside one typed function, rather than spreading casts through the loaders.
