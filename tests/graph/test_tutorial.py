import json

from typed_example import biotope, prepare, tutorial_commands


def test_the_tutorial_commands_build_the_graph_it_describes(tmp_path):
    root = prepare(tmp_path)
    graph_commands = [command for command in tutorial_commands() if command[0] == "graph"]
    assert graph_commands
    for command in graph_commands:
        result = biotope(root, *command)
        assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((root / "graph/build/run.json").read_text())["graph_objects"] == {"nodes": 3, "edges": 2}
    assert (root / "graph/metagraph.html").is_file()
