#!/usr/bin/env python3
"""Run the shared CQ1--CQ7 checks recursively over cumulative V2 examples.

Run from DMP_examples: python3 run_all_cqs.py
Uses check_cqs.py for IRI-based encodings and check_special_cqs.py for
original RDF-star (Jena 5.3.0) and N3 formulae (optional RDFLib).
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

EXTENSIONS = {".ttl", ".trig", ".nq", ".nquads", ".nt", ".n3", ".ttlstar", ".ntstar"}
FIELDS = ["file", "query", "status", "rows", "exit_code", "detail"]


def find_star_arq():
    import os
    home = os.environ.get("JENA53_HOME")
    return str(Path(home) / "bin/arq") if home else ""


def classify(path, relative, content):
    parts = list(relative.parts[:-1]) + [relative.stem]
    if any(re.search(r"(^|[-_. ])v1($|[-_. ])", part, re.I) for part in parts):
        return "SKIPPED_V1", "V1-only files are outside the cumulative V2 CQ test."
    if path.suffix.lower() == ".n3":
        return "SPECIAL_N3", None
    if ("rdf-star" in path.name.lower() or "rdfstar" in path.name.lower()
            or path.suffix.lower() in {".ttlstar", ".ntstar"}
            or re.search(r"<<(?!\s*\()", content)):
        return "SPECIAL_STAR", None
    if not (re.search(r"\b[A-Za-z_][\w-]*:V2\b", content)
            or "<https://example.org/example/V2>" in content):
        return "SKIPPED_NO_V2", "No V2 reference found; this check expects the small cumulative V2 example."
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path(__file__).resolve().parents[1] / "examples/running-example/v2")
    parser.add_argument("--queries", type=Path, default=Path(__file__).resolve().parent / "competency-questions")
    parser.add_argument("--arq", default="arq")
    parser.add_argument("--arq-star", default=find_star_arq(), help="Path to Jena 5.3.0 bin/arq")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checker = Path(__file__).resolve().with_name("check_cqs.py")
    special_checker = checker.with_name("check_special_cqs.py")
    if not checker.is_file():
        parser.error("Keep check_cqs.py beside run_all_cqs.py")
    if not args.examples.is_dir():
        parser.error(f"Example directory not found: {args.examples}")
    for i in range(1, 8):
        if not (args.queries / f"cq{i}.rq").is_file():
            parser.error(f"Missing query: {args.queries / f'cq{i}.rq'}")
    files = sorted(p for p in args.examples.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not files:
        parser.error("No supported file extensions found under the example directory")
    output = args.output or Path(__file__).resolve().parent / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("Output directory already exists; choose a new one")
    summary = []
    matrix = []
    for index, path in enumerate(files, 1):
        relative = path.relative_to(args.examples)
        label = str(relative)
        try:
            content = path.read_text(encoding="utf-8")
            status, detail = classify(path, relative, content)
        except (OSError, UnicodeError) as error:
            status, detail = "ERROR", str(error)
        matrix_row = {"file": label}
        special = status in {"SPECIAL_N3", "SPECIAL_STAR"}
        if status and not special:
            print(f"{label}: {status} - {detail}")
            for i in range(1, 8):
                query = f"CQ{i}"
                summary.append(dict(file=label, query=query, status=status, rows="", exit_code="", detail=detail))
                matrix_row[query] = status
            matrix.append(matrix_row)
            continue
        destination = output / f"{index:03d}-{path.stem}"
        if special:
            command = [sys.executable, str(special_checker), "--kind",
                       "n3" if status == "SPECIAL_N3" else "rdf-star",
                       "--data", str(path.resolve()), "--output", str(destination.resolve())]
            if status == "SPECIAL_STAR" and args.arq_star:
                command.extend(["--arq", str(Path(args.arq_star).expanduser())])
        else:
            command = [sys.executable, str(checker), "--data", str(path.resolve()),
                       "--queries", str(args.queries.resolve()), "--arq", args.arq,
                       "--output", str(destination.resolve())]
        run = subprocess.run(command, capture_output=True, text=True)
        (output / f"{index:03d}-runner.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        report = destination / "summary.csv"
        if report.exists():
            with report.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                summary.append({"file": label, **row})
                matrix_row[row["query"]] = row["status"]
            print(f"{label}: " + ", ".join(f"{r['query']}={r['status']}" for r in rows))
        else:
            detail = (run.stderr or run.stdout or "Runner produced no summary").strip()
            print(f"{label}: ERROR - {detail}")
            for i in range(1, 8):
                query = f"CQ{i}"
                summary.append(dict(file=label, query=query, status="ERROR", rows="", exit_code=run.returncode, detail=detail))
                matrix_row[query] = "ERROR"
        matrix.append(matrix_row)
    for filename, fields, rows in [
        ("summary-all.csv", FIELDS, summary),
        ("matrix.csv", ["file"] + [f"CQ{i}" for i in range(1, 8)], matrix),
    ]:
        with (output / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    (output / "scan-metadata.json").write_text(json.dumps({
        "examples": str(args.examples.resolve()), "queries": str(args.queries.resolve()),
        "file_count": len(files), "arq": args.arq, "arq_star": args.arq_star,
        "scope": "Cumulative S1--S5 V2 examples; shared IRI queries, RDF-star projection, RDFLib N3 procedure",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Combined results: {output / 'summary-all.csv'}")
    print(f"Matrix for the paper: {output / 'matrix.csv'}")
    return 1 if any(row["status"] in {"MISMATCH", "ERROR"} for row in summary) else 0


if __name__ == "__main__":
    sys.exit(main())
