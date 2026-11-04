from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = ""

    @classmethod
    def load(cls, path: str | Path) -> Project:
        data = yaml.safe_load(Path(path).read_text()) or {}
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            keys = ", ".join(str(error["loc"][0]) for error in exc.errors() if error["loc"]) or "its content"
            raise ValueError(f"{path} holds one key, purpose, a text; remove or fix {keys}") from None

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.model_dump(), sort_keys=False, allow_unicode=True))


def resolve_project_path(start: Path | None = None) -> Path:
    return (start if start is not None else Path.cwd()) / ".biotope" / "project.yaml"


def find_project(start: Path | None = None) -> Path | None:
    cur = (start if start is not None else Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (candidate := resolve_project_path(parent)).is_file():
            return candidate
    return None
