"""``biotope get`` — the universal ingress verb.

Brings external data into the project tree and bakes its Croissant manifest in
one shot, recording where the data came from (``dct:source`` + a fetch
timestamp). Dispatches on the shape of ``source``:

* **local file** — ``biotope get /scratch/data/foo.csv`` (copy + bake)
* **local directory** — ``biotope get /scratch/data/source_pull`` (recursive copy + bake)
* **http(s) file/page** — ``biotope get https://example.com/data.csv`` (download + bake)
* **website scrape** — ``biotope get --crawl --depth 2 https://example.com/topic/``

Unsupported transports (``s3://``, ``scp://``, …) are reported as not-yet-supported
and tracked as follow-up issues. ``biotope add`` remains the verb for data that
already lives inside the project tree.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

import click
import requests
from rich.progress import Progress, SpinnerColumn, TextColumn

from biotope.commands.add import (
    _add_file,
    _apply_dataset_metadata,
    _apply_pipeline_state,
    _bake_directory,
    _default_overrides,
    _generate_biotope_scaffold_from_baked,
    _resolve_dataset_ref,
)
from biotope.metadata import (
    SOURCE_KEY,
    make_file_object,
    merge_metadata,
    parse_key_value_pairs,
    resolve_target,
    set_source,
)
from biotope.scrape import ScrapeError, crawl
from biotope.utils import (
    find_biotope_root,
    is_git_repo,
    load_project_metadata,
    stage_git_changes,
)


# Transports recognised but deliberately deferred to follow-up issues.
_DEFERRED_SCHEMES = frozenset({"s3", "gs", "gcs", "scp", "sftp", "ftp", "ssh", "azure", "abfs", "abfss"})


def download_file(url: str, output_dir: Path) -> Path | None:
    """Download a file from URL with progress bar."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Get filename from URL or Content-Disposition header
        filename = None
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip('"')

        if not filename:
            filename = Path(urlparse(url).path).name

        # The filename is server-controlled (Content-Disposition or URL path):
        # reduce it to a bare basename so a malicious ``../../etc/foo`` or
        # ``/abs/path`` can't escape ``output_dir`` and write arbitrary files.
        filename = Path(filename).name
        if not filename or set(filename) <= {"."}:
            filename = "downloaded_file"

        output_path = output_dir / filename

        total_size = int(response.headers.get("content-length", 0))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Downloading {filename}...", total=total_size)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

        return output_path
    except Exception as e:
        click.echo(f"Error downloading file: {e}", err=True)
        return None


def _classify_source(source: str) -> str:
    """Classify a source string as ``"http"``, ``"local"``, or ``"unsupported"``."""
    scheme = urlparse(source).scheme.lower()
    if scheme in ("http", "https"):
        return "http"
    if scheme in _DEFERRED_SCHEMES:
        return "unsupported"
    # Everything else — no scheme, ``file://``, Windows drive letters — is a path.
    return "local"


def _normalize_local_source(source: str) -> Path:
    """Resolve a local source string (``file://`` URL or plain path) to a Path."""
    parsed = urlparse(source)
    if parsed.scheme == "file":
        return Path(url2pathname(parsed.path))
    return Path(source).expanduser()


def _is_within(path: Path, root: Path) -> bool:
    """Return True if ``path`` is ``root`` or lives underneath it."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _display(path: Path, biotope_root: Path) -> str:
    """Render ``path`` relative to the project root when possible, else absolute."""
    try:
        return str(path.relative_to(biotope_root))
    except ValueError:
        return str(path)


def _build_overrides(
    biotope_root: Path,
    *,
    status: str | None,
    name: str | None,
    description: str | None,
    license_value: str | None,
    creator: str | None,
    creator_email: str | None,
    url: str | None,
    citation: str | None,
    version: str | None,
    keywords: tuple[str, ...],
    access_restrictions: str | None,
    legal_obligations: str | None,
    collaboration_partner: str | None,
    rai_pairs: tuple[str, ...],
    derived_from: tuple[str, ...],
    fetched_at: str,
) -> dict[str, Any]:
    """Assemble the add-style overrides dict from ``get``'s CLI flags."""
    try:
        rai_fields = parse_key_value_pairs(rai_pairs, "--rai")
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    try:
        resolved_provenance = [_resolve_dataset_ref(ref, biotope_root) for ref in derived_from]
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    return {
        "name": name,
        "description": description,
        "license": license_value,
        "creator": creator,
        "creator_email": creator_email,
        "url": url,
        "citation": citation,
        "version": version,
        "keywords": list(keywords),
        "access_restrictions": access_restrictions,
        "legal_obligations": legal_obligations,
        "collaboration_partner": collaboration_partner,
        "rai_fields": rai_fields,
        "status_override": status,
        "derived_from": resolved_provenance,
        "source": None,
        "fetched_at": fetched_at,
    }


def _call_biotope_add(
    file_path: Path,
    biotope_root: Path,
    overrides: dict[str, Any] | None = None,
) -> bool:
    """Bake a single-file manifest for ``file_path`` and stage it in Git."""
    overrides = overrides if overrides is not None else _default_overrides()
    try:
        datasets_dir = biotope_root / ".biotope" / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)

        success = _add_file(
            file_path,
            biotope_root,
            datasets_dir,
            force=False,
            overrides=overrides,
        )

        if success:
            stage_git_changes(biotope_root)

        return success

    except FileNotFoundError:
        click.echo(f"❌ File not found: {file_path}", err=True)
        return False
    except PermissionError:
        click.echo(f"❌ Permission denied accessing: {file_path}", err=True)
        return False
    except Exception as e:  # noqa: BLE001
        click.echo(f"❌ Failed to add file to biotope project: {e}", err=True)
        return False


def _next_steps_file() -> None:
    """Echo the standard post-ingest next steps for a single tracked file."""
    click.echo("\n💡 Next steps:")
    click.echo("  1. Run 'biotope status' to see staged files")
    click.echo("  2. Run 'biotope annotate --staged' to create metadata")
    click.echo("  3. Run 'biotope commit -m \"message\"' to save changes")


def _ensure_project(ctx: click.Context, into: str) -> tuple[Path, Path | None]:
    """Find the biotope root, scaffolding one in ``into`` if outside a project.

    Returns ``(biotope_root, autoinit_dir)`` where ``autoinit_dir`` is non-None
    only when a project was just scaffolded (so the caller knows to land data at
    the new root rather than under ``into`` again).
    """
    biotope_root = find_biotope_root()
    if biotope_root:
        return biotope_root, None

    from biotope.commands.init import init as init_cmd

    output_path = Path(into)
    output_path.mkdir(parents=True, exist_ok=True)
    click.echo(f"📦 No biotope project found; initialising one at {output_path}")
    ctx.invoke(init_cmd, name=".", dir=output_path, no_prompt=True)
    biotope_root = find_biotope_root(start=output_path)
    if not biotope_root:
        click.echo("❌ Failed to initialise biotope project.")
        raise click.Abort
    return biotope_root, output_path


def _ingest_local_file(
    src: Path,
    dest_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    no_add: bool,
) -> None:
    """Copy a local file into the project and bake its manifest."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / src.name
    if dest_file.resolve() == src:
        click.echo(f"❌ Source and destination are the same file: {src}")
        raise click.Abort

    click.echo(f"📥 Copying file: {src} → {_display(dest_file, biotope_root)}")
    shutil.copy2(src, dest_file)
    click.echo(f"✅ Copied: {_display(dest_file, biotope_root)}")

    if no_add:
        click.echo("\n💡 File copied. To add to biotope project:")
        click.echo(f"  biotope add {_display(dest_file, biotope_root)}")
        return

    click.echo("📁 Adding file to biotope project...")
    if _call_biotope_add(dest_file, biotope_root, overrides):
        click.echo("✅ File added to biotope project")
        _next_steps_file()
    else:
        click.echo("⚠️  File copied but not added to biotope project")
        click.echo(f"   You can manually add it with: biotope add {_display(dest_file, biotope_root)}")


def _ingest_local_dir(
    src: Path,
    dest_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    no_add: bool,
) -> None:
    """Recursively copy a local directory into the project and bake one manifest."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / src.name

    click.echo(f"📥 Copying directory: {src} → {_display(dest_path, biotope_root)}")
    # Skip symlinks rather than dereference them: following links from an
    # untrusted source could copy external secrets into the project (and a
    # link to a parent dir would loop). The project stays self-contained.
    skipped_links: list[str] = []

    def _ignore_symlinks(directory: str, names: list[str]) -> list[str]:
        ignored = [name for name in names if (Path(directory) / name).is_symlink()]
        skipped_links.extend(str(Path(directory) / name) for name in ignored)
        return ignored

    shutil.copytree(src, dest_path, dirs_exist_ok=True, ignore=_ignore_symlinks)
    if skipped_links:
        click.echo(f"⚠️  Skipped {len(skipped_links)} symlink(s) for self-containment (copied real files only).")
    n_files = sum(1 for p in dest_path.rglob("*") if p.is_file())
    click.echo(f"✅ Copied {n_files} file(s) into {_display(dest_path, biotope_root)}")

    if no_add:
        click.echo("\n💡 Directory copied. To add to biotope project:")
        click.echo(f"  biotope add {_display(dest_path, biotope_root)}")
        return

    click.echo("📁 Baking directory manifest...")
    baked = _bake_directory(dest_path, biotope_root, overrides)
    if baked is None:
        click.echo("⚠️  Directory copied but no manifest was baked.")
        click.echo(f"   You can retry with: biotope add {_display(dest_path, biotope_root)}")
        return

    metadata_dict, n_source_files = baked
    stage_git_changes(biotope_root)
    _generate_biotope_scaffold_from_baked(dest_path.resolve(), metadata_dict, biotope_root)

    target = resolve_target(dest_path.resolve(), biotope_root)
    n_record_sets = len(metadata_dict.get("recordSet", []))
    click.echo(
        f"✨ Generated {_display(target.metadata_path, biotope_root)} "
        f"({n_source_files} source file(s), {n_record_sets} record set(s))"
    )
    click.echo("\n💡 Next steps:")
    click.echo(f"  • Review {_display(dest_path / '.biotope.yaml', biotope_root)}")
    click.echo(f"    Then: biotope annotate apply {_display(dest_path, biotope_root)}")
    click.echo("  • Map data into the knowledge graph: biotope map")
    click.echo('  • Finally: biotope commit -m "message"')


def _handle_local(
    source: str,
    dest_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    no_add: bool,
) -> None:
    """Validate and dispatch a local file/directory ingress."""
    src = _normalize_local_source(source)
    if not src.exists():
        click.echo(f"❌ Source not found: {source}")
        raise click.Abort

    src_abs = src.resolve()
    if _is_within(src_abs, biotope_root.resolve()):
        rel = src_abs.relative_to(biotope_root.resolve())
        click.echo(f"❌ '{source}' is already inside the project ({rel}).")
        click.echo(f"   Use 'biotope add {rel}' to register data already in the tree.")
        raise click.Abort

    overrides = {**overrides, "source": str(src_abs)}
    if src_abs.is_dir():
        _ingest_local_dir(src_abs, dest_dir, biotope_root, overrides, no_add)
    else:
        _ingest_local_file(src_abs, dest_dir, biotope_root, overrides, no_add)


def _handle_http(
    source: str,
    dest_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    no_add: bool,
) -> None:
    """Download a single http(s) file/page into the project and bake its manifest."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"📥 Downloading file from: {source}")
    downloaded_file = download_file(source, dest_dir)
    if not downloaded_file:
        click.echo("❌ Failed to download file")
        raise click.Abort
    click.echo(f"✅ Downloaded: {downloaded_file}")

    if no_add:
        click.echo("\n💡 File downloaded. To add to biotope project:")
        click.echo(f"  biotope add {downloaded_file}")
        return

    overrides = {**overrides, "source": source}
    click.echo("📁 Adding file to biotope project...")
    if _call_biotope_add(downloaded_file, biotope_root, overrides):
        click.echo("✅ File added to biotope project")
        _next_steps_file()
    else:
        click.echo("⚠️  File downloaded but not added to biotope project")
        click.echo(f"   You can manually add it with: biotope add {downloaded_file}")


def _bake_scrape_manifest(
    result,
    dataset_dir: Path,
    biotope_root: Path,
    seed_url: str,
    overrides: dict[str, Any],
):
    """Write one manifest covering all scraped pages, with per-page provenance."""
    defaults = load_project_metadata(biotope_root)
    fetched_at = overrides.get("fetched_at") or datetime.now(tz=timezone.utc).isoformat()
    # Resolve both sides so ``relative_to`` is robust to symlinked roots
    # (e.g. macOS /tmp → /private/tmp).
    root = biotope_root.resolve()
    dataset_dir = dataset_dir.resolve()
    rel = dataset_dir.relative_to(root)

    metadata = merge_metadata(
        {
            "name": overrides.get("name") or str(rel),
            "description": (
                overrides.get("description") or defaults.get("description") or f"Pages scraped from {seed_url}"
            ),
            "distribution": [],
            "dateCreated": fetched_at,
        }
    )

    for page in result.pages:
        file_object = make_file_object((dataset_dir / page.relpath).resolve(), root)
        # Per-page provenance: record where THIS page came from, inline on the
        # FileObject, so the manifest can answer it without the dataset-level field.
        file_object[SOURCE_KEY] = page.url
        metadata["distribution"].append(file_object)

    _apply_dataset_metadata(metadata, defaults, overrides, root)
    _apply_pipeline_state(metadata, overrides)
    set_source(metadata, seed_url, fetched_at)

    target = resolve_target(dataset_dir, root)
    target.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target.metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    return metadata, target


def _handle_scrape(
    source: str,
    dest_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    no_add: bool,
    *,
    depth: int,
    max_pages: int,
    rate: float,
    respect_robots: bool,
) -> None:
    """Bounded-crawl an http(s) site and bake one manifest over the saved pages."""
    host = urlparse(source).netloc
    safe_host = host.replace(":", "_") or "site"
    dataset_dir = dest_dir / safe_host

    robots_note = "" if respect_robots else ", ignoring robots.txt"
    click.echo(f"🕸️  Crawling {source} (depth {depth}, ≤{max_pages} pages, {rate} req/s{robots_note})")
    try:
        result = crawl(
            source,
            dataset_dir,
            depth=depth,
            max_pages=max_pages,
            rate=rate,
            respect_robots=respect_robots,
            echo=click.echo,
        )
    except ScrapeError as exc:
        click.echo(f"❌ {exc}")
        raise click.Abort from exc

    if not result.pages:
        click.echo("❌ No pages saved — nothing matched, or all candidates were blocked or failed.")
        if result.skipped:
            click.echo(f"   ({len(result.skipped)} URL(s) skipped; first: {result.skipped[0][1]})")
        raise click.Abort

    click.echo(f"✅ Saved {len(result.pages)} page(s) under {_display(dataset_dir, biotope_root)}")
    if result.skipped:
        click.echo(f"   ({len(result.skipped)} URL(s) skipped)")

    if no_add:
        click.echo("\n💡 Pages saved. To add to biotope project:")
        click.echo(f"  biotope add {_display(dataset_dir, biotope_root)}")
        return

    overrides = {**overrides, "source": source}
    _metadata, target = _bake_scrape_manifest(result, dataset_dir, biotope_root, source, overrides)
    stage_git_changes(biotope_root)
    click.echo(f"✨ Baked manifest: {_display(target.metadata_path, biotope_root)}")
    click.echo("\n💡 Next steps:")
    click.echo(f"  1. Review {_display(target.metadata_path, biotope_root)} (one FileObject per page)")
    click.echo("  2. Process the raw HTML into a derived artifact, then 'biotope add ... --derived-from'")
    click.echo("  3. Run 'biotope commit -m \"message\"' to save changes")


@click.command()
@click.argument("source")
@click.option(
    "--into",
    "--output-dir",
    "-o",
    "into",
    type=click.Path(file_okay=False),
    default="data",
    help="Project subdirectory the data lands in (default: data). The source's basename is preserved underneath it.",
)
@click.option(
    "--no-add",
    is_flag=True,
    help="Bring the data in without baking a manifest / tracking it.",
)
@click.option(
    "--status",
    "status",
    type=click.Choice(["raw", "processed"]),
    default=None,
    help="Override pipeline state. Default: classify like 'biotope add' "
    "(structured data → processed, documents/HTML → raw).",
)
@click.option(
    "--crawl", "crawl_mode", is_flag=True, help="Crawl a website instead of fetching one file (http(s) only)."
)
@click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=1,
    show_default=True,
    help="Crawl: link-following hops from the seed.",
)
@click.option(
    "--max-pages", type=click.IntRange(min=1), default=50, show_default=True, help="Crawl: cap on pages saved."
)
@click.option(
    "--rate",
    type=click.FloatRange(min=0.0, min_open=True),
    default=1.0,
    show_default=True,
    help="Crawl: requests per second.",
)
@click.option("--ignore-robots", is_flag=True, help="Crawl: do not consult robots.txt.")
@click.option("--name", help="Dataset name override")
@click.option("--description", help="Dataset description override")
@click.option("--license", "license_value", help="Dataset license")
@click.option("--creator", help="Dataset creator name")
@click.option("--creator-email", help="Dataset creator email")
@click.option("--url", help="Dataset homepage URL")
@click.option("--citation", help="Dataset citation text")
@click.option("--version", help="Dataset version")
@click.option("--keyword", "keywords", multiple=True, help="Dataset keyword (repeatable)")
@click.option("--access-restrictions", help="Dataset access restrictions")
@click.option("--legal-obligations", help="Dataset legal obligations")
@click.option("--collaboration-partner", help="Dataset collaboration partner")
@click.option("--rai", "rai_pairs", multiple=True, help="Croissant RAI field as KEY=VALUE")
@click.option(
    "--derived-from",
    "derived_from",
    multiple=True,
    help="Record this dataset as derived from another (repeatable). Pass a "
    "dataset reference — data path, manifest path, or dataset name.",
)
@click.pass_context
def get(
    ctx: click.Context,
    source: str,
    into: str,
    no_add: bool,
    status: str | None,
    crawl_mode: bool,
    depth: int,
    max_pages: int,
    rate: float,
    ignore_robots: bool,
    name: str | None,
    description: str | None,
    license_value: str | None,
    creator: str | None,
    creator_email: str | None,
    url: str | None,
    citation: str | None,
    version: str | None,
    keywords: tuple[str, ...],
    access_restrictions: str | None,
    legal_obligations: str | None,
    collaboration_partner: str | None,
    rai_pairs: tuple[str, ...],
    derived_from: tuple[str, ...],
) -> None:
    """Bring data into the project from a path, URL, or website, and track it.

    SOURCE may be a local file or directory, an http(s) URL, or (with --crawl)
    a website to crawl. The data is copied/downloaded into the project under
    --into, its Croissant manifest is baked, and its origin is recorded
    (dct:source + fetch timestamp). If run outside a biotope project, one is
    scaffolded in --into first.
    """
    source_type = _classify_source(source)
    if source_type == "unsupported":
        scheme = urlparse(source).scheme
        click.echo(f"❌ Unsupported source '{scheme}://…'. Transports like s3://, gs://, and scp:// are deferred")
        click.echo("   to follow-up issues (see #22). Supported: local paths, directories, and http(s) URLs.")
        raise click.Abort

    if crawl_mode and source_type != "http":
        click.echo("❌ --crawl requires an http(s) URL.")
        raise click.Abort

    biotope_root, autoinit_dir = _ensure_project(ctx, into)

    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init'.")
        raise click.Abort

    fetched_at = datetime.now(tz=timezone.utc).isoformat()
    overrides = _build_overrides(
        biotope_root,
        status=status,
        name=name,
        description=description,
        license_value=license_value,
        creator=creator,
        creator_email=creator_email,
        url=url,
        citation=citation,
        version=version,
        keywords=keywords,
        access_restrictions=access_restrictions,
        legal_obligations=legal_obligations,
        collaboration_partner=collaboration_partner,
        rai_pairs=rai_pairs,
        derived_from=derived_from,
        fetched_at=fetched_at,
    )

    # When a project was just scaffolded, it lives at ``into`` — land data at the
    # new root rather than nesting ``into`` inside itself again.
    dest_dir = biotope_root if autoinit_dir is not None else biotope_root / Path(into)

    # ``--into`` must stay inside the project tree. An absolute value or a
    # ``..`` escape would otherwise dump data outside the project (and crash the
    # bake step), since ``biotope_root / Path(abs)`` discards the root.
    if not _is_within(dest_dir.resolve(), biotope_root.resolve()):
        raise click.BadParameter("--into must be a subdirectory inside the project root.", param_hint="--into")

    if source_type == "local":
        _handle_local(source, dest_dir, biotope_root, overrides, no_add)
    elif crawl_mode:
        _handle_scrape(
            source,
            dest_dir,
            biotope_root,
            overrides,
            no_add,
            depth=depth,
            max_pages=max_pages,
            rate=rate,
            respect_robots=not ignore_robots,
        )
    else:
        _handle_http(source, dest_dir, biotope_root, overrides, no_add)
