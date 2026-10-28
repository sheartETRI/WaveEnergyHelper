"""코드 사용 경로와 검증 자료 색인을 재생성한다. 코드·데이터 이동이나 삭제는 하지 않는다.

실행: python scripts/maintain_inventory.py
산출: docs/inventory/{modules,artifacts}.csv
정적 import는 함수 내부도 포함하며, 동적 패널 등록과 문자열 참조를 별도로 기록한다.
참조가 없다는 사실은 미사용의 증거가 아니다.
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ("analysis", "charts", "config", "data", "display", "indicators", "narration",
             "notify", "scripts", "tracking", "utils", "validation", "tests")
ENTRYPOINTS = ("main", "scripts.alarm_cli", "scripts.push_alarms")


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_inventory():
    files = [ROOT / "main.py", ROOT / "plot_btcusdt_ma.py"]
    files += [p for d in CODE_DIRS for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts]
    files = sorted(p for p in files if p.is_file())
    modules = {p.relative_to(ROOT).with_suffix("").as_posix().replace("/", "."): p for p in files}
    texts = {m: p.read_text(encoding="utf-8-sig") for m, p in modules.items()}
    imports, strings, executable = {}, {}, {}
    for m, text in texts.items():
        tree = ast.parse(text)
        refs, literals = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                refs.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                refs.add(n.module)
                refs.update(n.module + "." + a.name for a in n.names)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                literals.add(n.value)
        imports[m] = refs & modules.keys()
        strings[m] = literals
        executable[m] = '__name__' in text and '__main__' in text
    reachable = set()
    pending = list(ENTRYPOINTS)
    while pending:
        m = pending.pop()
        if m in reachable:
            continue
        reachable.add(m)
        pending.extend(imports.get(m, set()) - reachable)
    registered = strings.get("display.panel_registry", set())
    rows = []
    for m, p in modules.items():
        consumers = [other for other, deps in imports.items() if m in deps]
        dynamic = m in registered
        if m.startswith("tests."):
            role = "테스트"
        elif m in ENTRYPOINTS:
            role = "운영 진입점"
        elif m in reachable:
            role = "운영 정적 의존 (조건부 import 포함)"
        elif dynamic:
            role = "이전 상세 UI 등록 패널"
        elif executable[m]:
            role = "수동 실행·연구 경로"
        elif consumers:
            role = "연구·호환·재현용 라이브러리"
        else:
            role = "사용처 미확인·보존"
        rows.append(dict(path=p.relative_to(ROOT).as_posix(), role=role,
                         runtime=m in reachable, registered_panel=dynamic,
                         manual_entry=executable[m], importers=";".join(sorted(consumers)),
                         dependencies=";".join(sorted(imports[m]))))
    write_csv(ROOT / "docs/inventory/modules.csv", rows,
              ["path", "role", "runtime", "registered_panel", "manual_entry", "importers", "dependencies"])

    documents = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8-sig")
                 for directory in ("docs", "validation")
                 for p in (ROOT / directory).rglob("*.md") if "archive" not in p.parts}
    artifacts = []
    for directory in ("validation", "docs"):
        for p in sorted((ROOT / directory).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in {".png", ".csv", ".json", ".md", ".txt"}:
                continue
            if any(part in {"inventory", "archive", "__pycache__"} for part in p.parts):
                continue
            refs = [m for m, text in texts.items() if p.name in text]
            doc_refs = [name for name, text in documents.items()
                        if name != p.relative_to(ROOT).as_posix() and p.name in text]
            candidates = [m for m in refs if m.startswith(("validation.", "scripts.")) and executable[m]]
            reports = [name for name in documents
                       if Path(name).stem.lower().removeprefix("report_") == p.stem.lower()]
            category = ("보고서·정의 문서" if p.suffix == ".md" else "그림" if p.suffix == ".png"
                        else "캐시" if any("cache" in part for part in p.parts)
                        else "누적 관측 기록" if "journal" in p.stem or "ledger" in p.stem
                        else "기준·연구 데이터")
            artifacts.append(dict(path=p.relative_to(ROOT).as_posix(), category=category,
                                  references=";".join(sorted(refs)),
                                  document_references=";".join(sorted(doc_refs)),
                                  producer_candidates=";".join(sorted(candidates)),
                                  experiment_sources=";".join(sorted(reports)),
                                  reproducibility="생성 후보·실험 조건 확인 필요" if candidates else "원본 보존·자동 재생성 미확인",
                                  policy="기존 경로 보존"))
    write_csv(ROOT / "docs/inventory/artifacts.csv", artifacts,
              ["path", "category", "references", "document_references", "producer_candidates",
               "experiment_sources", "reproducibility", "policy"])
    return len(rows), len(artifacts)


if __name__ == "__main__":
    modules, artifacts = build_inventory()
    print(f"모듈 {modules}개, 자료 {artifacts}개 색인 갱신")
