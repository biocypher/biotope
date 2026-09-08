"""Load and validate a ``mapping.yaml`` file."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from biotope.croissant.mapping.model import Mapping


class MappingLoadError(ValueError):
    """An unreadable or invalid mapping, with its filename and actionable detail."""


def load_mapping(path: str | Path) -> Mapping:
    """Load a mapping; report file, YAML and definition errors with their location."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, UnicodeError) as exc:
        raise MappingLoadError(f"Could not read mapping {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise MappingLoadError(f"Invalid mapping {path}{location}: {problem}") from exc
    try:
        return Mapping.model_validate(data if data is not None else {})
    except ValidationError as exc:
        details = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "mapping"
            details.append(f"{location}: {error['msg']}")
            if error["loc"][:1] == ("relations",) and error["loc"][-2:] in (("source", "value"), ("target", "value")):
                details.append("Define endpoint constants under ids and reference them with use: <name>.")
        raise MappingLoadError(f"Invalid mapping {path}:\n" + "\n".join(details)) from exc


def set_relation_deferred(mapping: Mapping, path: Path, name: str, *, deferred: bool) -> None:
    """Change only a relation's flag, preserving comments and YAML presentation.

    Parser marks locate the edit. Validate the complete result before writing;
    aliases that would also change another binding require an explicit edit.
    """
    if mapping.relations[name].deferred == deferred:
        return
    with path.open(encoding="utf-8", newline="") as stream:
        text = stream.read()
    root = yaml.compose(text)
    try:
        relations = next(value for key, value in root.value if key.value == "relations")
        node = next(value for key, value in relations.value if key.value == name)
    except StopIteration as exc:
        raise MappingLoadError(
            f"Cannot edit an inherited relation in {path}; set relations.{name}.deferred manually."
        ) from exc
    flag = next((value for key, value in node.value if key.value == "deferred"), None)
    value = "true" if deferred else "false"
    if flag is not None:
        start, end, replacement = flag.start_mark.index, flag.end_mark.index, value
    elif node.flow_style:
        start = node.value[-1][1].end_mark.index if node.value else node.end_mark.index - 1
        end = start
        replacement = (", " if node.value else "") + f"deferred: {value}"
    else:
        first_key = node.value[0][0]
        start = end = first_key.start_mark.index
        newline = "\r\n" if "\r\n" in text else "\n"
        replacement = f"deferred: {value}{newline}" + " " * first_key.start_mark.column
    edited = text[:start] + replacement + text[end:]
    relation = mapping.relations[name].model_copy(update={"deferred": deferred})
    expected = mapping.model_copy(update={"relations": {**mapping.relations, name: relation}})
    try:
        actual = Mapping.model_validate(yaml.safe_load(edited))
    except (yaml.YAMLError, ValidationError) as exc:
        raise MappingLoadError(f"Cannot safely edit {path}; set relations.{name}.deferred manually.") from exc
    if actual != expected:
        raise MappingLoadError(
            f"Editing {path} would change another binding through a YAML alias; edit the flag manually."
        )
    path.write_text(edited, encoding="utf-8", newline="")


def dump_mapping(mapping: Mapping, path: str | Path) -> None:
    """Serialise a :class:`Mapping` to ``path`` as YAML."""
    from biotope.croissant.mapping.render import render_mapping_yaml

    Path(path).write_text(render_mapping_yaml(mapping))


def discover_mapping_paths(mappings_dir: Path) -> list[Path]:
    """Return mapping YAML paths, preferring `*.mapping.yaml` over `*.yaml` duplicates."""
    candidates = sorted(mappings_dir.glob("*.yaml")) + sorted(mappings_dir.glob("*.yml"))
    selected: dict[str, Path] = {}

    for path in candidates:
        key = _mapping_identity(path)
        existing = selected.get(key)
        if existing is None or _mapping_path_rank(path) > _mapping_path_rank(existing):
            selected[key] = path

    return list(selected.values())


def _mapping_identity(path: Path) -> str:
    name = path.name
    for suffix in (".mapping.yaml", ".mapping.yml", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _mapping_path_rank(path: Path) -> int:
    name = path.name
    if name.endswith((".mapping.yaml", ".mapping.yml")):
        return 2
    if name.endswith((".yaml", ".yml")):
        return 1
    return 0
