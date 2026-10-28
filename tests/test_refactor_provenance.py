"""구조 변경이 고정 정의·함수 본문을 바꾸지 않았는지 출처와 대조한다."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integrity


def definitions(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def test_moved_definitions_match_recorded_original_ast():
    manifest = json.loads((ROOT / "config/refactor_provenance.json").read_text(encoding="utf-8"))
    for row in manifest["functions"]:
        node = definitions(ROOT / row["target"])[row["name"]]
        actual = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        assert actual == row["ast_sha256"], row


def test_manifest_matches_git_source():
    manifest = json.loads((ROOT / "config/refactor_provenance.json").read_text(encoding="utf-8"))
    cache = {}
    for row in manifest["functions"]:
        key = (row["commit"], row["source"])
        if key not in cache:
            result = subprocess.run(["git", "show", f"{key[0]}:{key[1]}"], cwd=ROOT, capture_output=True)
            if result.returncode:
                pytest.skip(f"출처 커밋 필요: {key[0]}")
            tree = ast.parse(result.stdout.decode("utf-8-sig"))
            cache[key] = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        expected = hashlib.sha256(ast.dump(cache[key][row["name"]], include_attributes=False).encode()).hexdigest()
        assert expected == row["ast_sha256"], row


def test_restored_documents_match_original_bytes():
    manifest = json.loads((ROOT / "docs/provenance.json").read_text(encoding="utf-8"))
    for row in manifest["restored_documents"]:
        blob = (ROOT / row["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(blob).hexdigest() == row["sha256"]


def test_shared_calculation_and_notification_have_no_ui_or_batch_imports():
    for directory in ("tracking", "notify"):
        for path in (ROOT / directory).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports = [node.module]
                assert not any(m.split(".")[0] in {"display", "validation", "charts"} for m in imports), (path, imports)
