# Biotope Get

!!! warning "Draft stage"

```
Biotope is in draft stage. Functionality may be missing or incomplete.
The API is subject to change.
```

`biotope get` is the universal **ingress** verb: it brings data into the project
tree from outside, bakes the Croissant manifest, and records where the data came
from — all in one shot. Use `biotope add` instead for data that already lives
inside the project (e.g. agent-produced derived artifacts).

`get` dispatches on the shape of the source:

| Source            | Example                                              | Behaviour             |
| ----------------- | ---------------------------------------------------- | --------------------- |
| Local file        | `biotope get /scratch/data/foo.csv`                  | copy + bake           |
| Local directory   | `biotope get /scratch/data/source_pull`              | recursive copy + bake |
| http(s) file/page | `biotope get https://example.com/data.csv`           | download + bake       |
| Website scrape    | `biotope get --crawl --depth 2 https://example.com/` | bounded crawl + bake  |

Every manifest baked by `get` records its origin as `dct:source` (the URL or
absolute path) plus a `biotope:fetchedAt` timestamp. For a scrape, each page's
`cr:FileObject` also carries its own `dct:source`, so the manifest can answer
"where did *this* page come from?".

## Command Signature

```bash
biotope get [OPTIONS] SOURCE
```

## Options

- `--into, --output-dir, -o`: project subdirectory the data lands in (default:
  `data`). The source's basename is preserved underneath it.
- `--no-add`: bring the data in without baking a manifest / tracking it.
- `--status [raw|processed]`: override pipeline state. Default: classify like
  `biotope add` (structured data → `processed`, documents/HTML → `raw`).
- `--crawl`: crawl a website instead of fetching one file (http(s) only).
- `--depth`: crawl link-following hops from the seed (default: 1).
- `--max-pages`: crawl cap on pages saved (default: 50).
- `--rate`: crawl requests per second (default: 1.0).
- `--ignore-robots`: crawl without consulting `robots.txt`.
- Dataset metadata overrides (same as `biotope add`): `--name`, `--description`,
  `--license`, `--creator`, `--creator-email`, `--url`, `--citation`,
  `--version`, `--keyword`, `--access-restrictions`, `--legal-obligations`,
  `--collaboration-partner`, `--rai KEY=VALUE`, `--derived-from`.

## Examples

### Copy a local file from a scratch mount

```bash
biotope get /scratch/data/experiment.csv --license CC-BY-4.0
# → data/experiment.csv  (+ .biotope/datasets/data/experiment.jsonld)
```

### Copy a local directory (one composite manifest)

```bash
biotope get /scratch/data/source_pull \
  --creator "Source Org" \
  --description "Whole pulled folder"
# → data/source_pull/…  (+ one manifest covering the tree, + .biotope.yaml)
```

### Download a file from a URL

```bash
biotope get https://example.com/data.csv
```

### Scrape a website (bounded, polite)

```bash
biotope get --crawl --depth 2 --max-pages 30 https://example.com/topic/
# → data/example.com/…  (one HTML file per page, one manifest)
```

The crawler stays on the seed's host, respects `robots.txt` (unless
`--ignore-robots`), and rate-limits to `--rate` requests per second.

## What It Does

1. Classifies the source (local path, http(s) URL, or website to crawl).
   Unsupported transports (`s3://`, `scp://`, …) are reported and deferred.
1. If run outside a biotope project, scaffolds one in `--into` first.
1. Copies / downloads / crawls the data into the project under `--into`.
1. Bakes the Croissant manifest (reusing the same machinery as `biotope add`).
1. Stamps `dct:source` + `biotope:fetchedAt` provenance on the manifest.
1. Stages `.biotope/` changes in Git.

## v1 scope for `--crawl`

Static HTML only. JS rendering, deep recursive crawls beyond the seeded depth,
cloud-storage transports, and authentication are deliberately out of scope and
tracked as follow-up issues.

::: biotope.commands.get
