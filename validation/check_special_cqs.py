#!/usr/bin/env python3
"""Representation-specific CQ checks: original RDF-star (Jena 5.3.0), N3 (RDFLib).

Uses the query files in special-queries/ beside this script. These are retained
in each result directory. Input is the ground single-content-triple S1--S5 example.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from check_cqs import EXPECTED, EX, DMP

XSD = "http://www.w3.org/2001/XMLSchema#"
DCT = "http://purl.org/dc/terms/"


def uri(value):
    return ("uri", value)


def literal(value, datatype=None, language=None):
    if datatype == XSD + "boolean":
        value = {"0": "false", "1": "true"}.get(value, value)
    return ("literal", value, datatype or XSD + "string", language or "")


CONTENT = {
    EX+"S1": (uri(EX+"images"), uri(DMP+"depositedIn"), uri("https://www.ebi.ac.uk/bioimage-archive/")),
    EX+"S2": (uri(EX+"images"), uri(DCT+"license"), uri("https://creativecommons.org/licenses/by/4.0/")),
    EX+"S3": (uri(EX+"images"), uri(DMP+"containsHumanOrSensitiveData"), literal("false", XSD+"boolean")),
    EX+"S4": (uri(EX+"images"), uri(DCT+"license"), uri("https://creativecommons.org/publicdomain/zero/1.0/")),
    EX+"S5": (uri(EX+"localCopy"), uri(DMP+"retentionPeriod"), literal("Ten years after project completion")),
}
LABELS = {frozenset([triple]): label for label, triple in CONTENT.items()}


def content_label(triples):
    key = frozenset(triples)
    return LABELS.get(key, "UNEXPECTED_FORMULA:" + repr(sorted(key, key=repr)))


def json_term(term):
    if term is None:
        raise ValueError("Missing projected triple component; see raw JSON result")
    if term.get("type") == "uri":
        return uri(term["value"])
    if term.get("type") in {"literal", "typed-literal"}:
        return literal(term["value"], term.get("datatype"), term.get("xml:lang"))
    raise ValueError("Unsupported projected component: " + repr(term))


def decode_star(payload, variables):
    expected_columns = []
    for v in variables:
        expected_columns.extend(["subject", "predicate", "object"] if v == "statement"
            else ["supersededSubject", "supersededPredicate", "supersededObject"]
            if v == "supersededStatement" else [v])
    if set(payload["head"]["vars"]) != set(expected_columns):
        raise ValueError("Unexpected columns in RDF-star projection")
    rows = []
    for row in payload["results"]["bindings"]:
        decoded = []
        for variable in variables:
            if variable in {"statement", "supersededStatement"}:
                fields = ["subject", "predicate", "object"] if variable == "statement" else ["supersededSubject", "supersededPredicate", "supersededObject"]
                decoded.append(content_label([tuple(json_term(row.get(f)) for f in fields)]))
            else:
                term = row.get(variable)
                if term is None:
                    decoded.append(None)
                elif term.get("type") == "uri":
                    decoded.append(term["value"])
                else:
                    raise ValueError("Expected IRI metadata value: " + repr(term))
        rows.append(tuple(decoded))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["rdf-star", "n3"], required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--arq", help="Jena 5.3.0 ARQ executable for RDF-star")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not args.data.is_file():
        parser.error("Input not found")
    args.output.mkdir(parents=True, exist_ok=False)
    metadata = {"kind": args.kind, "input": str(args.data.resolve()),
        "sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "comparison": "decode ground single-triple content to S1--S5; distinct rows; ignore ordering",
        "query_directory": "special-queries/" + args.kind}
    unavailable = None
    graph = None
    arq = None
    if args.kind == "rdf-star":
        arq = shutil.which(args.arq or "")
        if not arq:
            unavailable = "Jena 5.3.0 ARQ not found. Set --arq-star /path/to/apache-jena-5.3.0/bin/arq on the batch runner."
        else:
            try:
                version = subprocess.run([arq, "--version"], capture_output=True, text=True, timeout=30)
                text = version.stdout + version.stderr
                metadata.update(arq=arq, version_output=text)
                if version.returncode or not re.search(r"\b5\.3\.0\b", text):
                    unavailable = "RDF-star branch requires Jena 5.3.0; detected version is different or unknown."
            except (OSError, subprocess.TimeoutExpired) as error:
                unavailable = str(error)
    else:
        try:
            import rdflib
            from rdflib import Graph, URIRef, Literal
            from rdflib.graph import QuotedGraph
        except ImportError:
            unavailable = "RDFLib missing: install it in this Python environment (python3 -m pip install rdflib==7.6.0)."
        if not unavailable:
            metadata["rdflib_version"] = rdflib.__version__
            try:
                graph = Graph().parse(args.data, format="n3")
            except Exception as error:
                metadata["parse_error"] = str(error)

    def n3_term(term):
        if isinstance(term, URIRef):
            return uri(str(term))
        if isinstance(term, Literal):
            return literal(str(term), str(term.datatype) if term.datatype else None, term.language)
        raise ValueError("Unsupported ground content term: " + repr(term))

    def decode_n3(term):
        if term is None:
            return None
        if isinstance(term, QuotedGraph):
            return content_label([tuple(n3_term(t) for t in triple) for triple in term])
        if isinstance(term, URIRef):
            return str(term)
        raise ValueError("Expected formula or IRI, got " + repr(term))

    summary = []
    for name, expected in EXPECTED.items():
        report = {"query": name.upper(), "status": "ERROR", "expected": expected}
        exit_code = None
        row_count = None
        try:
            if unavailable:
                report.update(status="NOT_TESTED", error=unavailable)
            else:
                query_file = Path(__file__).resolve().parent / "special-queries" / args.kind / (name + ".rq")
                query = query_file.read_text(encoding="utf-8")
                (args.output / (name + ".rq")).write_text(query, encoding="utf-8")
                if args.kind == "rdf-star":
                    command = [arq, "--data=" + str(args.data.resolve()),
                               "--query=" + str(query_file), "--results=JSON"]
                    report["command"] = command
                    result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
                    exit_code = result.returncode
                    (args.output / (name + ".json")).write_text(result.stdout, encoding="utf-8")
                    (args.output / (name + ".log")).write_text(result.stderr, encoding="utf-8")
                    if exit_code:
                        raise ValueError("ARQ failed; see query log")
                    payload = json.loads(result.stdout)
                    rows = decode_star(payload, expected["vars"])
                else:
                    if graph is None:
                        raise ValueError("N3 parse failed: " + metadata.get("parse_error", "unknown error"))
                    result = graph.query(query)
                    raw = list(result)
                    if [str(v) for v in result.vars] != expected["vars"]:
                        raise ValueError("Unexpected N3 query columns")
                    rows = [tuple(decode_n3(term) for term in row) for row in raw]
                    (args.output / (name + "-raw.json")).write_text(json.dumps({
                        "variables": expected["vars"],
                        "raw_term_representations": [[repr(v) for v in row] for row in raw],
                        "decoded_rows": rows,
                    }, indent=2) + "\n", encoding="utf-8")
                    exit_code = 0
                row_count = len(rows)
                actual = set(rows)
                wanted = {tuple(r) for r in expected["rows"]}
                report.update(status="MATCH" if actual == wanted else "MISMATCH",
                    decoded_distinct_results=sorted(actual, key=repr),
                    missing=sorted(wanted-actual, key=repr), unexpected=sorted(actual-wanted, key=repr))
        except Exception as error:
            report["error"] = str(error)
        (args.output / (name + "-check.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        row = dict(query=name.upper(), status=report["status"], rows=row_count,
                   exit_code=exit_code, detail=report.get("error", ""))
        summary.append(row)
        print(name.upper() + ": " + report["status"] + (" - " + row["detail"] if row["detail"] else ""))
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "status", "rows", "exit_code", "detail"])
        writer.writeheader(); writer.writerows(summary)
    return 1 if any(r["status"] in {"ERROR", "MISMATCH"} for r in summary) else 0


if __name__ == "__main__":
    sys.exit(main())
