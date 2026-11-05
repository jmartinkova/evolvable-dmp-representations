# Evolvable DMP Representations

Research materials supporting **Towards Evolvable Data Management Plans: Representing the Contents**, by Jana Martínková, Marek Suchánek, and Robert Pergl.

This repository connects a conceptual approach to evolving data management plans (DMPs) with RDF encodings, competency-question checks, and a synthetic parsing benchmark. A semantic Statement is distinguished from its encoding and from the version-specific inclusion that carries its lifecycle state.

## Contents

| Directory | Contents |
| --- | --- |
| `examples/running-example/v1/` | Ten encodings of the first microscopy DMP version |
| `examples/running-example/v2/` | Ten cumulative V2 encodings, including preserved V1 inclusion records |
| `examples/existing-dmp/` | Ten proof-of-concept encodings of one existing DMP |
| `validation/competency-questions/` | Shared CQ1–CQ7 SPARQL queries |
| `validation/special-queries/` | RDF-star and Notation3 query variants required by the checker |
| `validation/*.py` | Query execution and expected-answer comparison scripts |
| `validation/results/final/` | Supplied final CQ run, including raw responses, checks, logs and metadata |
| `benchmark/headers/`, `benchmark/templates/` | Shared headers and per-Statement generation templates |
| `benchmark/datasets/` | Exact supplied synthetic datasets, including the unmeasured N3 files |
| `benchmark/generator.py` | Deterministic dataset generator |
| `benchmark/benchmark.py`, `benchmark/ParseBenchmark.java` | Python orchestration and Java streaming parsing harness |
| `benchmark/calculate-metrics.py` | Derivation of the reported metrics |
| `benchmark/results/final/` | Final measurements |

## Running example and expected answers

V1 plans microscopy-image deposition in the BioImage Archive and release under CC BY 4.0. V2 records deposition and release under CC0 1.0, retains the original licensing commitment as Deprecated, and introduces a ten-year local-copy retention commitment attributed to an illustrative institutional policy. Both versions record that the dataset contains no human or sensitive data.

| ID | Content | V1 | V2 |
| --- | --- | --- | --- |
| S1 | Deposition | Planned | Completed |
| S2 | CC BY 4.0 release | Planned | Deprecated |
| S3 | No human or sensitive data | No assigned state | No assigned state |
| S4 | CC0 1.0 release | Not recorded | Completed; supersedes S2 |
| S5 | Local archival retention | Not recorded | Planned; external policy source |

CQ1 retrieves S1, S4 and S5 in V2; CQ2 retrieves all five; CQ3 retrieves S1–S3 with their states in both versions; CQ4 retrieves new S4 and S5; CQ5 retrieves Planned for S5 in V2; CQ6 retrieves S5 with its external policy source; CQ7 retrieves S4 supersedes S2. Full expected bindings are defined in `validation/check_cqs.py`.

The scenario and institutional policy are fictional. Decomposition, status assignment and supersession are manual. Missing state differs from explicitly assigned Undefined; this example has no positive Undefined case. The small examples and benchmark use one content triple per conceptual Statement.

## Reproduce competency-question checks

Requirements: Python 3.9 or newer; Apache Jena ARQ 6.2.0 for the IRI-based encodings; Jena ARQ 5.3.0 for original quoted RDF-star; RDFLib 7.6.0 for Notation3. The recorded Python version was 3.13.11. Use the same Python environment for installing RDFLib and invoking the runner.

From the repository root:

```bash
python3 -m venv .venv-cq
.venv-cq/bin/python -m pip install -r requirements-cq.txt
.venv-cq/bin/python validation/run_all_cqs.py \
  --arq="/absolute/path/to/apache-jena-6.2.0/bin/arq" \
  --arq-star="/absolute/path/to/apache-jena-5.3.0/bin/arq"
```

Both executable paths are installation-specific. `--arq` defaults to `arq` on PATH; the RDF-star executable can alternatively be set via `JENA53_HOME`. Use explicit paths to avoid accidentally substituting a different version. Jena distributions are not bundled.

The runner scans `examples/running-example/v2/` and writes a new timestamped directory under `validation/results/`. Existing results are not overwritten. Input and query directories can be overridden using `--examples` and `--queries`.

MATCH means agreement with expected bindings after ignoring row ordering and duplicate decoded rows. MISMATCH means different answers; ERROR means an execution failure; NOT_TESTED means a case was not run and is not a pass. Unbound states are distinct from explicit state values.

RDF-star content is projected to subject, predicate and object and mapped to S1–S5 for comparison. Notation3 uses dedicated RDFLib formula-aware handling; this does not establish portable standard SPARQL support. The checker is specific to the small example, not arbitrary DMPs. The supplied final run reports **70 MATCH results: seven questions for ten encodings**. Packaging inspection confirmed the saved results and the available special-branch input hashes; it did not freshly rerun Jena or RDFLib.

## Existing DMP

The manually represented document is Pölzler, T. (2023), *Data Management Plan: Making Morality Impartial: An Experimental Investigation of the Veil of Ignorance*, available through [DMPonline public plans](https://dmponline.dcc.ac.uk/public_plans).

This is one proof-of-concept application, not a representative corpus or empirical analysis of observed version histories. The original document is not included in this package.

## Reproduce synthetic datasets

Each template instance encodes one licensing Statement about a distinct dataset, together with source attribution and inclusion in V1 as Planned. Supporting records are included in overhead but are not counted as additional benchmark Statements. Sizes are 10, 100, 1000 and 10000 Statements.

```bash
cd benchmark
python3 generator.py
```

## Reproduce parsing measurements

Install a JDK providing `java` and `javac`, Jena 5.3.0 and 6.2.0. The original run used Oracle Java SE/HotSpot 25.0.2, Python 3.13.11 and macOS 26.5.1 on ARM64 with ten logical CPUs; exact recorded details are in `benchmark/results/final/`.

From `benchmark/`:

```bash
python3 benchmark.py \
  --jena53="/absolute/path/to/apache-jena-5.3.0" \
  --jena62="/absolute/path/to/apache-jena-6.2.0"
```

The benchmark uses an in-memory byte buffer, a fresh parser per iteration and a non-storing streaming sink. JVM/Jena initialization, file loading and validation/counting precede measurement. No graph store or indexes are constructed.

For each file/version combination:

- Three separate JVM processes.
- Warm-up until **both** at least ten parses and at least five seconds of accumulated timed parsing have completed per process.
- Twenty measured parses per process: sixty timings per combination, nested within three processes.
- `System.nanoTime()` timing; `-Xms256m -Xmx1g`; no explicit garbage collection request.
- Task order shuffled with seed `20261020`.

Common supported encodings are measured in both versions; original RDF-star only in 5.3.0 and RDF 1.2 only in 6.2.0. N3 quoted formulae are excluded. Results are written to a new `benchmark-results-*` directory. Keep the same protocol and environment when comparing measurements; the full run is not instantaneous.

## Metrics

- **Inflation:** emitted triple/quad records divided by generated Statement count. These are parser events, not unique stored records or memory consumption.
- **Parsing time per Statement:** median dataset parsing time divided by Statement count. `median_ms_per_statement` is in milliseconds; multiply by 1000 for microseconds.
- **Scaling factor:** time-growth ratio divided by Statement-count growth ratio for adjacent sizes within the same encoding, serialization and Jena version. One indicates proportional growth over that interval, not asymptotic complexity.

Interpret timing comparisons within the same Jena version. This benchmark does not measure disk throughput, storage ingestion, query execution, automatic interpretation or version comparison.

## Citation

If you use the RDF examples, validation scripts, or benchmark
materials from this repository, please cite the archived release:

[Towards Evolvable Data Management Plans: Representing the Contents — Supporting Materials](https://doi.org/10.5281/zenodo.23983890)

For the full citation and BibTeX export, see the Zenodo record.

Contact: Jana Martínková, jana.martinkova@cvut.cz.
