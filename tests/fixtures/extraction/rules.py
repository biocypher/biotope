class LineExtractor:
    name = "lines"

    def __init__(self, settings):
        self.version = settings["version"]
        self.line = settings["line"]
        self.settings = {"line": self.line}

    def extract(self, document, schema):
        text = document.text.splitlines()[self.line - 1]
        return [{"name": {"value": text, "locator": f"line {self.line}"}, "group": {"value": None}, "methods": []}]
