import ast
from pathlib import Path


def test_runtime_source_does_not_import_subprocess_or_shell_commands():
    source_root = Path(__file__).parents[1] / "src" / "ps2ripper"
    forbidden_calls = {"system", "popen", "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve"}
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "subprocess" for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess", path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in forbidden_calls
                ), path
