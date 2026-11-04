#!/usr/bin/env python3
"""Run CQ1--CQ7 with Jena ARQ and compare SPARQL JSON answers.

Default input: example/v2/rdf12.ttl
Default queries: competency-questions/cq1.rq ... cq7.rq
Requires Python 3.9+ and Jena; no third-party Python packages.
Supports the shared IRI-based Statement queries, not N3 formulae or direct RDF-star terms.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

EX = "https://example.org/example/"
DMP = "https://example.org/dmp-vocab/"
POLICY = "https://example.org/policies/data-retention"
EXPECTED = {
    "cq1": {"vars": ["statement", "state"], "rows": [
        [EX+"S1", DMP+"Completed"], [EX+"S4", DMP+"Completed"], [EX+"S5", DMP+"Planned"]]},
    "cq2": {"vars": ["statement", "state"], "rows": [
        [EX+"S1", DMP+"Completed"], [EX+"S2", DMP+"Deprecated"], [EX+"S3", None],
        [EX+"S4", DMP+"Completed"], [EX+"S5", DMP+"Planned"]]},
    "cq3": {"vars": ["statement", "stateV1", "stateV2"], "rows": [
        [EX+"S1", DMP+"Planned", DMP+"Completed"],
        [EX+"S2", DMP+"Planned", DMP+"Deprecated"], [EX+"S3", None, None]]},
    "cq4": {"vars": ["statement"], "rows": [[EX+"S4"], [EX+"S5"]]},
    "cq5": {"vars": ["statement", "state"], "rows": [[EX+"S5", DMP+"Planned"]]},
    "cq6": {"vars": ["statement", "source"], "rows": [[EX+"S5", POLICY]]},
    "cq7": {"vars": ["statement", "supersededStatement"], "rows": [[EX+"S4", EX+"S2"]]},
}


def compare_answers(payload, expected):
    variables = expected["vars"]
    if set(payload["head"]["vars"]) != set(variables):
        raise ValueError("Query columns do not match this CQ: expected " + ", ".join(variables)
                         + ". Use the current CQ1--CQ7 numbering and IRI-based queries.")
    actual = set()
    for row in payload["results"]["bindings"]:
        values = []
        for variable in variables:
            term = row.get(variable)
            if term is None:
                values.append(None)
            elif term.get("type") == "uri":
                values.append(term["value"])
            else:
                raise ValueError("Expected an IRI reference, got " + repr(term)
                                 + ". Formula/quoted-triple projections need a separate checker.")
        actual.add(tuple(values))
    wanted = {tuple(row) for row in expected["rows"]}
    return actual, wanted, actual == wanted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "examples/running-example/v2/rdf12.ttl")
    parser.add_argument("--queries", type=Path, default=Path(__file__).resolve().parent / "competency-questions")
    parser.add_argument("--arq", default="arq")
    parser.add_argument("--output", type=Path, help="New output directory; must not already exist")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.data.suffix.lower() == ".n3":
        parser.error("N3 quoted formulae are not supported by this ARQ procedure; use the RDFLib N3 checker.")
    if "rdf-star" in args.data.name.lower() or "rdfstar" in args.data.name.lower():
        parser.error("Direct RDF-star needs the intended parser version and formula-aware result checking; not this procedure.")
    if not args.data.is_file():
        parser.error(f"Input file not found: {args.data}")
    missing = [str(args.queries / f"cq{i}.rq") for i in range(1, 8)
               if not (args.queries / f"cq{i}.rq").is_file()]
    if missing:
        parser.error("Missing queries (current numbering CQ1--CQ7): " + ", ".join(missing))
    arq = shutil.which(args.arq)
    if not arq:
        parser.error("ARQ executable not found; set --arq /path/to/jena/bin/arq")
    output = args.output or Path("cq-results") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"Output directory already exists: {output}; choose a new directory")
    dataset_flag = "--data"
    metadata = {
        "utc": datetime.now(timezone.utc).isoformat(), "input": str(args.data.resolve()),
        "queries": str(args.queries.resolve()), "arq": arq,
        "python": platform.python_version(), "platform": platform.platform(),
        "comparison": "IRI terms and unbound cells; distinct result sets, ignoring order",
    }
    try:
        version = subprocess.run([arq, "--version"], capture_output=True, text=True, timeout=30)
        metadata["arq_version_output"] = version.stdout + version.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        metadata["arq_version_output"] = str(error)
    summary = []
    for name, expected in EXPECTED.items():
        command = [arq, f"{dataset_flag}={args.data.resolve()}",
                   f"--query={(args.queries / (name + '.rq')).resolve()}", "--results=JSON"]
        report = {"query": name, "command": command, "expected": expected, "status": "ERROR"}
        exit_code = None
        rows_count = None
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
            exit_code = result.returncode
            (output / f"{name}.json").write_text(result.stdout, encoding="utf-8")
            (output / f"{name}.log").write_text(result.stderr, encoding="utf-8")
            if result.returncode:
                raise ValueError("ARQ failed; see " + name + ".log")
            payload = json.loads(result.stdout)
            actual, wanted, match = compare_answers(payload, expected)
            rows_count = len(payload["results"]["bindings"])
            report.update(status="MATCH" if match else "MISMATCH", raw_rows=rows_count,
                          missing=sorted(wanted-actual, key=repr), unexpected=sorted(actual-wanted, key=repr))
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            report["error"] = str(error)
        (output / f"{name}-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary.append({"query": name.upper(), "status": report["status"],
                        "rows": rows_count, "exit_code": exit_code, "detail": report.get("error", "")})
        print(f"{name.upper()}: {report['status']}" + (" - " + report["error"] if "error" in report else ""))
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "status", "rows", "exit_code", "detail"])
        writer.writeheader()
        writer.writerows(summary)
    print(f"Saved results to {output}")
    return 0 if all(row["status"] == "MATCH" for row in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
