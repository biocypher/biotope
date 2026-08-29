# Ideas — not built

Gaps noticed while making biotope work with croissant-baker's
compression-decoupling refactor. None was needed for compatibility.

Finding ids (G*, B*) are from `docs/2026-08-27_biotope-gap-analysis.md` in the
daria_mvp project, which measured biotope 0.8.0 against 94 GiB of spatial-omics
data.

## Coverage reporting

`add` forwards the baker's coverage summary to stdout and reads no further into
the report — its shape is new and still moving.

- **Persist the figures.** A `biotope:scanSummary` block in the manifest would
  let `queue` and `status` answer "how much of this deposit was read" without
  re-baking. Today the answer lives only in terminal scrollback.
- **Pass `--report PATH` through.** The summary counts by reason; it does not
  name files. That currently means invoking `croissant-baker` directly.
- **Retire the hand-rolled coverage reconstruction.** `_append_uncovered_file_objects`
  and `_iter_directory_files` re-derive by directory walk what `scan_report`
  now states, and cannot tell "no handler claimed it" from "the handler failed".
- **Let `claims()` say why it refused.** A handler that recognises a file by
  extension and then rejects its content warns on its own logger
  (`missing Parquet PAR1 footer magic`), and the pipeline separately reports the
  file as `no_handler`. Two lines for one file, and the specific reason — the
  useful one — never reaches the scan report or `--report`. Returning a refusal
  rather than `False` would fix both, at the cost of changing the contract for
  all nine handlers.

## Pipeline state

- **`raw` / `processed` answers the wrong question (G7).** It reports whether
  the baker parsed something, not whether the dataset is annotated.
- **Annotation state is not measured against a schema (G6),** because there is
  no target-schema object for it to resolve against (G2).

## Manifest correctness

- **Fabricated license, version, datePublished (B1).** With none supplied the
  baker invents them and biotope passes them through — but only for datasets
  with at least one record set, so two manifest shapes exist. Spans both packages.
- **Creator email is the local git user (B2).** Name and email resolve
  independently, so every third-party creator is stamped with whoever ran the
  command.
- **`--rebake` discards annotation.** It rewrites the manifest wholesale. Must
  be settled before a field-level annotation surface is worth adding.
- **`annotate apply` drops unrecognised keys silently (B7)** and still prints
  `✅ Updated`.

## Formats — croissant-baker's side

Still undescribed in a 10x Xenium / Visium HD corpus, worst first:

| Format | Why it matters |
|---|---|
| `.soft` | GEO's native metadata export — where every sample-level field actually lives |
| `.h5` | AnnData `.obs` / `.var` is a common hiding place for sample metadata |
| `.zarr.zip` | Xenium analysis output; reported as an archive and not opened |
| `.btf` | Visium HD BigTIFF. The image handler reads BigTIFF magic already; it needs the extension |
| `.ome.tif` OME-XML | Header already read for dimensions; `PhysicalSizeX` and channel names are not surfaced |
| `.vlf.txt` | JSON behind a `.txt` name — needs content sniffing, not extension dispatch |

On the existing CSV path: a comment-character option, so a 10x `probe_set.csv`
parses instead of failing on its `#` preamble. That preamble carries
`panel_name` and `reference_genome`.
