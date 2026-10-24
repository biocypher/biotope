class LineExtractor:
    name = "lines"

    def __init__(self, settings):
        self.version = settings["version"]
        self.line = settings["line"]
        self.settings = {"line": self.line}

    def extract(self, document, schema):
        if self.line < 1:
            raise ValueError("line numbers start at 1")
        text = document.text.splitlines()[self.line - 1]
        return [{"name": {"value": text, "locator": f"line {self.line}"}, "group": {"value": None}, "methods": []}]
