import hashlib
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from biotope.cli import cli


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/extraction"
KEY = "sk-test-0123456789-sentinel"
LIVE_KEY = os.environ.get("OPENROUTER_API_KEY")


class Endpoint:
    def __init__(self) -> None:
        self.rules: list[tuple[str, object]] = []
        self.requests: list[dict] = []
        self.delay = 0.0
        self.busy = 0
        self.most_busy = 0
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def reply(self, marker: str, answer: object, times: int | None = None) -> None:
        self.rules.insert(0, [marker, answer, times])

    def answer(self, text: str) -> object:
        with self.lock:
            rule = next((rule for rule in self.rules if rule[0] in text), None)
            if rule is None:
                return 500
            if rule[2] is not None:
                rule[2] -= 1
                if rule[2] == 0:
                    self.rules.remove(rule)
            return rule[1]

    def serving(self, change: int) -> None:
        with self.lock:
            self.busy += change
            self.most_busy = max(self.most_busy, self.busy)

    def _handler(self):
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                endpoint.serving(1)
                threading.Event().wait(endpoint.delay)
                endpoint.serving(-1)
                with endpoint.lock:
                    endpoint.requests.append(
                        {"path": self.path, "body": body, "authorization": self.headers.get("Authorization")}
                    )
                answer = endpoint.answer(body["messages"][-1]["content"])
                if isinstance(answer, int):
                    self.send_response(answer)
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "refused by the fake endpoint"}}')
                    return
                content = answer if answer is None or isinstance(answer, str) else json.dumps(answer)
                payload = {"choices": [{"message": {"role": "assistant", "content": content}}]}
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return Handler


def quoted(value, quote=None):
    return {"value": value, "quote": value if quote is None else quote}


LIND = {
    "record": {
        "name": quoted("Mara Lind", "Dr. Mara Lind"),
        "group": quoted("Spatial Atlas Group"),
        "methods": [quoted("spatial transcriptomics"), quoted("single-cell RNA sequencing")],
    }
}
OKAFOR = {
    "record": {
        "name": quoted("Chidi Okafor"),
        "group": quoted("Machine Learning for Tissues Group", "Machine Learning for Tissues Lab"),
        "methods": [quoted("graph neural networks")],
    }
}
ROWS = {
    "Pre-proposal": "Pre-proposal 15 January 2027 no funding",
    "Full proposal": "Full proposal 30 April 2027 1 500 000 EUR",
    "Renewal": "Renewal 1 March 2029 750 000 EUR",
}


def funding_round(name, deadline, budget, row=None):
    row = row or ROWS[name]
    return {"round": quoted(name, row), "deadline": quoted(deadline, row), "budget": quoted(budget, row)}


ROUNDS = {
    "records": [
        funding_round("Pre-proposal", "15 January 2027", None),
        funding_round("Full proposal", "30 April 2027", "1 500 000 EUR"),
        funding_round("Renewal", "1 March 2029", "750 000 EUR"),
    ]
}


class Study:
    def __init__(self, root: Path, endpoint: Endpoint) -> None:
        self.root = root
        self.endpoint = endpoint

    def run(self, *args: str):
        return CliRunner().invoke(cli, list(args))

    def extract(self, *args: str):
        result = CliRunner(mix_stderr=False).invoke(cli, ["extract", *args, "--json"])
        return result, json.loads(result.stdout)

    def configure(self, **settings):
        path = self.root / ".biotope/config.yaml"
        config = yaml.safe_load(path.read_text())
        config["extraction"] = {key: value for key, value in settings.items() if value is not None}
        path.write_text(yaml.safe_dump(config, sort_keys=False))

    def records(self, name: str) -> list[dict]:
        lines = (self.root / "extracted" / f"{name}.jsonl").read_text().splitlines()
        return [json.loads(line) for line in lines]

    def text(self, document: str) -> str:
        digest = hashlib.sha256((self.root / document).read_bytes()).hexdigest()
        [cached] = (self.root / ".biotope/texts").glob(f"{digest}*.txt")
        return cached.read_text(encoding="utf-8")

    def snapshot(self) -> dict[str, bytes]:
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(self.root).parts
        }


@pytest.fixture
def endpoint():
    served = Endpoint()
    served.reply("Mara Lind", LIND)
    served.reply("Chidi Okafor", OKAFOR)
    served.reply("Funding rounds", ROUNDS)
    yield served
    served.server.shutdown()


@pytest.fixture
def study(tmp_path, monkeypatch, endpoint):
    for variable, value in (
        ("GIT_AUTHOR_NAME", "Test"),
        ("GIT_AUTHOR_EMAIL", "test@example.org"),
        ("GIT_COMMITTER_NAME", "Test"),
        ("GIT_COMMITTER_EMAIL", "test@example.org"),
    ):
        monkeypatch.setenv(variable, value)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    root = tmp_path / "study"
    project = Study(root, endpoint)
    created = project.run("init", "study", "--dir", str(tmp_path), "--no-prompt")
    assert created.exit_code == 0, created.output
    monkeypatch.chdir(root)
    (root / "data/pages").mkdir(parents=True)
    (root / "data/calls").mkdir(parents=True)
    for page in ("lind.html", "okafor.html"):
        shutil.copy(FIXTURES / page, root / "data/pages" / page)
    shutil.copy(FIXTURES / "call.pdf", root / "data/calls/call.pdf")
    (root / "extraction").mkdir()
    shutil.copy(FIXTURES / "schemas.py", root / "extraction/schemas.py")
    project.configure(extractor="llm", endpoint=endpoint.url, model="test/model", key_env="OPENROUTER_API_KEY")
    added = project.run("add", "data/pages", "data/calls")
    assert added.exit_code == 0, added.output
    return project
