# Project layout

Biotope is one part of a project, not the whole project. It writes only in its own
places, never writes to git, keeps what people write about a dataset in one
annotation file next to the data, and names every file and table by its path. New
data of the same shape therefore rebuilds with commands only.

## Biotope's places

A biotope project sits at the root of the host repository, beside the project's
own code: `.biotope/` and `graph/` next to `src/`, for example. Inside the project,
biotope writes only in these places, and in the files you name to `mv`, `rm` or
`--out`:

- `.biotope/`: metadata and technical state. `config.yaml`; `project.yaml`, the
  purpose that `biotope map` records; the Croissant descriptions in
  `.biotope/datasets/`, each named after its data's whole path, such as
  `.biotope/datasets/data/study.v2.jsonld` for the folder `data/study.v2` and
  `.biotope/datasets/data/raw/people.csv.jsonld` for the file
  `data/raw/people.csv`; the contract revisions in `.biotope/contracts/`; and the
  extraction state in `.biotope/extraction/`. Commit all of it. The document texts
  in `.biotope/texts/` and an interrupted run's progress in `.biotope/progress/`
  ignore themselves in git.
- `graph/`: the graph workspace, the project's code and the graph it builds,
  extraction schemas in `graph/extraction/<kind>.py` included. The
  `graph/.gitignore` that `biotope graph scaffold` writes ignores `graph/build/`,
  the `graph/.build-*/` folders a build stages in, and `graph/metagraph.html`.
- `data/extracted/<schema>.jsonl`: the records `biotope extract run` writes by
  default. Commit them. `--out` names another path.
- Annotation files, next to each dataset you add: `<folder>/.biotope.yaml` or
  `<file>.biotope.yaml`. Commit them.
- The root `.gitignore`, which `biotope init` writes only when the project has none.

`data/` is a convention, not a rule: `biotope add` takes any folder, and the
annotation file goes next to it. The `.gitignore` that `init` writes keeps data
files under `data/` out of git and commits annotation files and extracted records:

```gitignore
/data/**
!/data/**/
!/data/**/*.biotope.yaml
!/data/extracted/**
__pycache__/
*.pyc
.venv/
```

`init` never changes an existing `.gitignore`. In a project that has one, replace
a `/data/` rule with `/data/**` and add the three exceptions: git cannot re-include
a file inside an ignored folder, so the exceptions do not work under `/data/`.

Replace an unanchored `data/` rule the same way. It ignores every folder named
`data` at any depth, and that includes `.biotope/datasets/data/`: descriptions
mirror the data path, so every description of a dataset under `data/` lives there
and git ignores all of them. Biotope warns about each ignored file it writes. If
other `data` folders must stay ignored, list each with a leading slash, such as
`/src/app/data/`.

## The graph workspace

`biotope graph scaffold` creates `graph/`; its `README.md` describes the layout.
Three parts of it follow fixed rules:

- **Topology.** Each node has a folder under `graph/topology/`, named after its
  class in snake_case, with the class in `node.py`. Each edge has its own file in
  the folder of its source node, the node whose ID type its `source` field uses,
  named after the edge class in snake_case:

  ```text
  graph/topology/
    __init__.py            TOPOLOGY registers every node and edge
    person/node.py         Person
    sample/node.py         Sample
    sample/from_person.py  FromPerson, from a sample to a person
  ```

  `biotope graph check` fails with `topology.layout`, naming the class and the file
  it belongs in, when a node or edge sits elsewhere. Other modules there, such as
  helpers and shared types, are free. The export reserves the property names
  `preferred_id` and `biotope_provenance_id`, and `graph check` reports either as
  `topology.reserved` before any build.

- **Extraction schemas** live in `graph/extraction/<kind>.py`. The scaffold lists
  `extraction` in the pipeline's `code_paths`, so `graph check` type-checks them
  and `run.json` records them with the rest of the graph code. Write them after
  `graph scaffold`, which refuses an existing `graph/`.

- **Dependencies.** `graph/pyproject.toml` declares the libraries the graph code
  uses. `graph check` warns about an undeclared import, and a build's `run.json`
  records the installed version of every declared distribution, every distribution
  the graph code imports, biotope, croissant-baker and pyright, and BioCypher when
  it writes the export.

## Git belongs to the project

Biotope does not presume or require git, and it never writes to git: no command
runs `git init`, stages or commits. Commit biotope's places with the rest of the
project, using git yourself. `biotope commit`, `log`, `push` and `pull`,
`init --no-git` and `init --visible` are retired, and `mv` works without git.

When a repository exists, biotope reads its ignore rules. Every command that
writes a file the project must commit (a description, a contract, a records file
or an annotation file) warns on stderr when git ignores it, and changes nothing:

```text
Warning: git ignores data/raw/samples.csv.biotope.yaml. Commit it with the project: add an exception to .gitignore.
```

`extract run` lists such files under `ignored` in its report. Without git or
without a repository, no warning appears.

`biotope status` lists the descriptions in `.biotope/datasets/` and reads neither
git nor data. `Current` means every source package generated from a description
pins its current revision, `Changed` names each package that pins another one,
and `No source` means no package was generated from it yet:

```text
Current   data
Changed   study
          graph/sources/study/samples: pinned 73a5e23963bf, now 43036e7de4d8
No source data/extracted/profile.jsonl
```

`biotope check-data` compares the data files with their recorded checksums.

Biotope writes no creator or licence that nobody gave: neither the git user nor
croissant-baker's default CC BY 4.0. A dataset gets one from its annotation file,
from `biotope add --creator` or `--license`, or from the project defaults that
`biotope config set-project-metadata` sets. What croissant-baker generates from the
data, such as a description or a creation date, stays.

## The annotation file

Each dataset has one sparse annotation file, the single place for everything people
and agents write about it. `biotope add` creates it, with a header comment and no
values, before any graph workspace exists:

- `biotope add data/study` creates `data/study/.biotope.yaml`;
- `biotope add data/raw/samples.csv` creates `data/raw/samples.csv.biotope.yaml`.

A value in the file wins over the data's, a missing value comes from the data, and
an empty value clears what the data says. For example:

```yaml
# What people write about this dataset. A value here wins over the data's; an empty value clears it.
description: People and reports of one synthetic study.
license:
creator: Ada Lovelace
file_sets:
  events/*.parquet: events
tables:
  push/people.csv#people:
    description: One row per person.
    key: person_id
    columns:
      person_id:
        description: The person's ID in the study's export.
        equivalentProperty: https://schema.org/identifier
```

- Top-level keys other than `tables` and `file_sets` are dataset fields, written
  into the description as Croissant keys: `name`, `description`, `license`,
  `creator`, `citeAs`, `keywords`, `url`, `version` and the like. A `creator`
  given as a name or a mapping, such as `{name: Ada Lovelace, email: ...}`, becomes
  a `Person`. Here `license:` is empty, so the description has no licence.
  `biotope:status` holds the workflow state you set, and `prov:wasDerivedFrom` a
  list of the dataset IDs this dataset was derived from.
- `file_sets` renames a file set: the key is its include pattern, such as
  `events/*.parquet`, the value the name you give it. The new name becomes the file
  set's ID.
- `tables` is keyed by table ID. A table takes a `description`, a `key` (a column
  name or a list of them) and other Croissant keys. `columns` is keyed by each
  column's name in the data and takes a `description`, an `equivalentProperty` and
  other Croissant keys.
- Column types and nullability belong in each source's `schema.py`, which the
  loader decodes into; do not write them here.

Edit the file by hand, or write values with commands. The commands write only the
values you give, never values inferred from the data, and keep your comments:

```bash
biotope add data/study --description "People and reports of one synthetic study." --license ""
biotope annotate set data/study --table 'push/people.csv#people' description="One row per person." key=person_id
biotope annotate set data/study --table 'push/people.csv#people' --column person_id \
  equivalentProperty=https://schema.org/identifier
```

- `biotope add` flags, on the first add or with `--rebake`, write dataset fields:
  `--name`, `--description`, `--license`, `--creator` and `--creator-email`,
  `--url`, `--citation` (written as `citeAs`), `--version`, `--keyword`
  (repeatable, written as `keywords`), `--access-restrictions`,
  `--legal-obligations`, `--collaboration-partner`, and `--rai KEY=VALUE`, written
  as given. `--status` writes `biotope:status` and `--derived-from` (repeatable)
  `prov:wasDerivedFrom`.
- `biotope mark DATA STATUS` writes `biotope:status`, and its `--derived-from`
  adds to `prov:wasDerivedFrom`.
- `biotope annotate set DATA KEY=VALUE...` writes into the annotation file of
  `DATA`, the path you added. Without `--table` the values describe the dataset,
  with `--table <ID>` that table, and with `--column <name>` that column. The ID
  may be written without its percent-encoding, such as `'x - y.csv#x - y'`. A
  repeated key makes a list, and an empty value clears. It refuses a table or
  column the description does not have.

The Croissant description in `.biotope/datasets/` is the data, as croissant-baker
describes it, with the annotation file over it. Never edit it by hand. Every
command that reads a description applies the annotation file's current content
and rewrites the description when the file changed, so a hand edit takes effect at
the next `graph check`, `graph build`, `source generate` or `map inspect` with no
other step. Each value the file replaces keeps the data's value under
`biotope:fromData`, so deleting a line brings the data's value back.

`biotope add --rebake <path>` describes the data again and applies the annotation
file again. It always succeeds and leaves the annotation file unchanged: every
annotation and every cleared value survives. When the file names a table or column
the data no longer has, `add` warns and names it.

The annotation file describes structure the data has; it cannot add any. A file
croissant-baker cannot parse still gets a file entry, with an ID from its path, and
its own source package. A document, such as a paper or a web page, goes through
[extraction](extraction.md): the extracted records become a dataset with tables
and fields of their own. Any other file is read by its own package's loader, which
decodes it with an established library into the fields you declare in its
`schema.py`.

## File and table IDs

An ID depends only on the item's path relative to the dataset root: the folder you
added, or a single file's folder. It never depends on listing order, other files,
the file's content or the machine. Content hashes are checksums, never IDs.

- A file's ID is its path in POSIX form and Unicode NFC. Letters, digits and
  `!$&'()*+,;=@-._~/` stay as they are; every other character is
  percent-encoded: `push/people.csv`, and `reports/Café report.html` becomes
  `reports/Café%20report.html`.
- A table's ID is its file's ID, `#` and the table's name in the file: the file
  name without its extensions for a single-table file (`push/people.csv#people`,
  `push/events.csv.gz#events`), the sheet name for a workbook, and the name
  croissant-baker gives each table inside other files, such as an HDF5 dataset
  (`cells/sample.h5ad#obs`) or a FHIR resource type, even while the file holds
  only one.
- A file set's ID is its name, which croissant-baker gives it, such as
  `events partition files`, and the annotation file can change. Its table's ID is
  `<file set name>#<table>`: `events%20partition%20files#events`, or
  `events#events` after the rename above.
- A field's ID is `<table ID>/<column>`: `push/people.csv#people/person_id`.
- A file whose one table has no columns, such as a JSON file holding only `{}`,
  is a file, not a table: `run/state.json` keeps that ID and gets a file package.
- `biotope add data/raw/samples.csv` adds a single file, whose root is its folder:
  its table is `samples.csv#samples`.

A new file leaves every other ID as it was, and a changed file keeps its own. Two
cases have no ID, and the bake fails, naming them:

```text
cannot give every file and table a stable ID: the paths push/People.csv and push/people.csv differ only in case
cannot give every file and table a stable ID: the file set name 'parts' is used 2 times, by the file sets of a/*.parquet and b/*.parquet; rename one
```

Rename one of the files, or rename one file set in the annotation file by its
include pattern, as in `file_sets: {a/*.parquet: a parts}`. No ID gets a suffix
that depends on order or on other files.

`biotope source generate` names packages and record classes after the IDs, with
the percent-encoding undone: the table `push/people.csv#people` gets the package
`push_people_csv_people` and the class `PushPeopleCsvPeople`, and
`reports/Lab%20results.csv#Lab%20results` gets `reports_Lab_results_csv_Lab_results`.
A file no table reads is named after its file name:
`docs/report.html` gets the package `report_html`. Both are yours to rename.

A description's packages sit under one root package, named after its last path
part: `.biotope/datasets/data/study.jsonld` gets `graph/sources/study/`. Two
datasets with the same last name, such as `data/a/raw` and `data/b/raw`, would
share the root `raw`, so the second one's first generation reports a conflict and
writes nothing. Name its root with `--package`:

```bash
biotope source generate .biotope/datasets/data/b/raw.jsonld --out graph/sources --package b_raw
```

Later generations, the refresh included, find the root that holds the description
without `--package`.

## Source revisions cover structure

A source package's `schema.py` pins the revision it was written against in
`__source_digest__`, and `biotope graph check` reports `source.drift` when the
description's revision differs. A revision covers structure only, meaning what a
source package's code depends on: fields and their nesting, column types,
nullability, keys, array shapes, references, where each field reads from, and the
files' paths, formats and patterns. It leaves out names, descriptions, equivalent
properties, examples, checksums, sizes and the JSON-LD `@context`.

- Descriptions and equivalent properties, in the annotation file or from the data,
  never fail `graph check`.
- A new column or a changed column type in the data, a key in the annotation file,
  or a changed file reference fails it with `source.drift` once: review the change
  against the schema and loader, then set `__source_digest__` to the revision the
  finding names.
- A change of a file's content alone fails neither `graph check` nor `graph build`.
  `biotope check-data` reports it.

## Refresh after new data

When new data of the same shape arrives, such as new rows, a new file, a
re-downloaded document or a same-named file in another folder, run:

```bash
biotope add --rebake data/study
biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
biotope graph check
biotope graph build
```

Run `add --rebake` once per changed dataset and `source generate` once per
description. No file needs a hand edit: every existing file and table keeps its ID,
so every source reads the same file as before, and the annotation file applies
again.

A new table or file gets a new package with a placeholder loader. The scaffold's
`graph/sources/__init__.py` selects every inventoried source, so `graph check`
then fails with `inventory.placeholder` until you write its loader or exclude it.
A project that rebuilds without anyone at hand selects its sources by name and
excludes the rest with one rule, written once:

```python
from biotope.graph import SourceContract

from .inventory import INVENTORY
from .study.push_people_csv_people import SOURCE as PEOPLE
from .study.report_html import SOURCE as REPORT


SOURCES: tuple[SourceContract, ...] = (PEOPLE, REPORT)
EXCLUDED_SOURCES: dict[str, str] = {
    source.name: "New data; select it once its loader is written" for source in INVENTORY if source not in SOURCES
}
```

`run.json` lists each excluded source with its reason, so new inputs stay visible.

## Move a file

`biotope mv data/study/push/people.csv data/study/current/people.csv` moves the
file and updates in one step everything that names it: its ID and its tables' IDs
in the description, the annotation file's keys for those tables, the IDs in its
source package's `schema.py` and, if the package was current, its
`__source_digest__`, and a records file's extraction state. A single file's
annotation file moves with it. `biotope mv -r` does the same for every file in a
folder and moves the descriptions of the datasets inside it; it changes nothing
when it cannot update one of them. `graph check` then passes, and the source reads
the file at its new path. `mv` refuses, changing nothing, to replace a file a
description holds or an existing annotation file, even with `--force`, and to give
a file a path that differs from another's only in case.

A move made outside biotope, by a file manager, `git mv` or a download script,
gives the file a new ID at the next refresh. `source generate` creates a package
for the new ID and reports the old one as orphaned, and `graph check` fails with
`inventory.orphan`, naming the old and the new ID:

```text
'push/people.csv#people' is no longer described by study.jsonld: its file 'push/people.csv' moved outside biotope to
'current/people.csv', now described as 'current/people.csv#people'. Declare the new ID in this package, or move the
file back, rebake and use biotope mv
```

A dataset that is a single file has no folder to rebake, so its refresh runs
`biotope add` on the file at its new path and `source generate` on the description
that names it. When exactly one description names a file that is gone and has the
same content, `add` moves that description and its annotation file to the new path,
and `graph check` fails in the same way.

To recover, move the file back, run `biotope add --rebake` on its dataset, or on
the file for a single-file dataset, move it with `biotope mv`, and delete the package
`source generate` created for the new path.
