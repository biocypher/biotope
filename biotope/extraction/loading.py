from __future__ import annotations

import hashlib
import importlib
import sys
import types
from pathlib import Path


def load_object(reference: str, root: Path | None = None) -> object:
    module_name, separator, attribute = reference.rpartition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"{reference!r}: name a class as path/to/module.py:Name or package.module:Name")
    if module_name.endswith(".py"):
        path = Path(module_name)
        if not path.is_absolute() and root is not None:
            path = root / path
        if not path.is_file():
            raise ValueError(f"{reference!r}: {path} does not exist")
        name = "biotope_project_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    else:
        module = importlib.import_module(module_name)
    try:
        return getattr(module, attribute)
    except AttributeError:
        raise ValueError(f"{reference!r}: {module_name} defines no {attribute}") from None
