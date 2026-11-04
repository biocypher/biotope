from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str
    purpose: str = ""
    required_entities: list[str] = Field(default_factory=list)
    required_relations: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    notes: str = ""

    @classmethod
    def load(cls, path: str | Path) -> Project:
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls.model_validate(data)

    def dump(self, path: str | Path) -> None:
        payload = self.model_dump(exclude_defaults=False)
        Path(path).write_text(yaml.safe_dump(payload, sort_keys=False))


def resolve_project_path(start: Path | None = None) -> Path:
    return (start if start is not None else Path.cwd()) / ".biotope" / "project.yaml"


def find_project(start: Path | None = None) -> Path | None:
    cur = (start if start is not None else Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (candidate := resolve_project_path(parent)).is_file():
            return candidate
    return None
