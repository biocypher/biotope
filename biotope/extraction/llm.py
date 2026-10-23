from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from typing import Any, cast

import requests

from biotope.extraction.contract import Document, ExtractionError
from biotope.extraction.schema import Schema


QUOTE = {
    "type": ["string", "null"],
    "description": (
        "The shortest span of the document text that states the value, copied character for character, "
        "never shortened, joined or reworded; for a value read from a table, the table's whole row. "
        "Null only when the value is null."
    ),
}
SYSTEM = (
    "You extract structured records from one document. Return JSON that matches the schema. "
    "Record only what the document states; use null or an empty list for anything it does not state. "
    "Give every value with its quote: text copied exactly from the document. "
    "When a value comes from a table, quote the table's whole row."
)
RETRIED = frozenset({408, 429, 500, 502, 503, 504})
ATTEMPTS = 3


class LLMExtractor:
    name = "llm"
    version = "1"

    def __init__(self, options: Mapping[str, object]) -> None:
        missing = [key for key in ("endpoint", "model", "key_env") if not options.get(key)]
        if missing:
            raise ValueError(f"Set {', '.join(f'extraction.{key}' for key in missing)} in .biotope/config.yaml")
        unknown = sorted(set(options) - {"endpoint", "model", "key_env"})
        if unknown:
            raise ValueError(f"The llm extractor has no setting {', '.join(unknown)}")
        self.endpoint = str(options["endpoint"]).rstrip("/")
        self.model = str(options["model"])
        variable = str(options["key_env"])
        key = os.environ.get(variable)
        if not key:
            raise ValueError(f"Set the environment variable {variable}, which extraction.key_env names")
        self._key = key
        self.settings = {"endpoint": self.endpoint, "model": self.model}

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Document text:\n\n{document.text}"},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.name, "strict": True, "schema": request_schema(schema)},
            },
        }
        answer = self._post(payload)
        try:
            content = answer["choices"][0]["message"]["content"]
            records = json.loads(content)["records"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ExtractionError(f"the model's answer is not the requested JSON: {self._clean(str(exc))}") from None
        if not isinstance(records, list):
            raise ExtractionError("the model's answer has no list of records")
        return cast(list[dict[str, Any]], records)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.endpoint}/chat/completions"
        headers = {"Authorization": f"Bearer {self._key}"}
        problem = ""
        for attempt in range(ATTEMPTS):
            if attempt:
                time.sleep(2**attempt)
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=600)
            except requests.RequestException as exc:
                problem = f"{url} could not be reached: {type(exc).__name__}"
                continue
            if response.status_code == 200:
                try:
                    return cast(dict[str, Any], response.json())
                except ValueError:
                    raise ExtractionError(f"{url} answered with invalid JSON") from None
            problem = f"{url} answered {response.status_code}: {self._clean(response.text[:300])}"
            if response.status_code not in RETRIED:
                break
        raise ExtractionError(problem)

    def _clean(self, text: str) -> str:
        return " ".join(text.replace(self._key, "***").split())


def request_schema(schema: Schema) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for item in schema.fields:
        quoted = {
            "type": "object",
            "properties": {"value": item.value_schema(), "quote": QUOTE},
            "required": ["value", "quote"],
            "additionalProperties": False,
        }
        if item.many:
            properties[item.name] = {"type": "array", "description": item.description, "items": quoted}
        else:
            properties[item.name] = {**quoted, "description": item.description}
    return schema.wrap(properties)
