import os, time, tracemalloc, psutil, csv
from rdflib import Graph, Dataset

# mapování přípon na formáty
EXT2FMT = {
    ".ttl": "turtle",
    ".nt": "nt",
    ".n3": "n3",
    ".trig": "trig",
    ".nq": "nquads",
    ".nquads": "nquads",
}

def benchmark(file, iterations=3):
    base, ext = os.path.splitext(file)
    fmt = EXT2FMT.get(ext.lower(), "turtle")

    parse_times, serialize_times, memories = [], [], []
    size_kb = os.path.getsize(file) / 1024

    for _ in range(iterations):
        proc = psutil.Process(os.getpid())

        # vyber správný kontejner
        if fmt in ("trig", "nquads"):
            g = Dataset()
        else:
            g = Graph()

        tracemalloc.start()
        t0 = time.perf_counter()
        g.parse(file, format=fmt)
        t1 = time.perf_counter()
        parse_times.append((t1 - t0) * 1000)
        tracemalloc.stop()

        memories.append(proc.memory_info().rss / (1024 * 1024))

        t0 = time.perf_counter()
        g.serialize(destination="tmp_out", format=fmt)
        t1 = time.perf_counter()
        serialize_times.append((t1 - t0) * 1000)

    return {
        "file": os.path.basename(file),
        "format": fmt,
        "triples": len(g),
        "size_kb": round(size_kb, 1),
        "parse_ms": round(sum(parse_times) / len(parse_times), 2),
        "serialize_ms": round(sum(serialize_times) / len(serialize_times), 2),
        "memory_mb": round(max(memories), 2),
    }

if __name__ == "__main__":
    in_dir = "datasets"
    results = []
    skip_files = {
        "rdf-12_10.nt", "rdf-12_100.nt", "rdf-12_1000.nt", "rdf-12_5000.nt",
        "rdf-12-annotated_10.ttl", "rdf-12-annotated_100.ttl", "rdf-12-annotated_1000.ttl", "rdf-12-annotated_5000.ttl",
        "rdf-12-quoted_10.ttl", "rdf-12-quoted_100.ttl", "rdf-12-quoted_1000.ttl", "rdf-12-quoted_5000.ttl",
        "rdf-star-annotated_10.ttl", "rdf-star-annotated_100.ttl", "rdf-star-annotated_1000.ttl", "rdf-star-annotated_5000.ttl",
        "rdf-star-quoted_10.ttl", "rdf-star-quoted_100.ttl", "rdf-star-quoted_1000.ttl", "rdf-star-quoted_5000.ttl",
    }

    for fname in os.listdir(in_dir):
        if fname.endswith(tuple(EXT2FMT.keys())) and not fname in skip_files:
            fpath = os.path.join(in_dir, fname)
            print(f"Benchmarking {fname} ...")
            result = benchmark(fpath)
            results.append(result)

    with open("benchmark_results.csv", "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["file", "format", "triples", "size_kb", "parse_ms", "serialize_ms", "memory_mb"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("Hotovo! Výsledky uložené do benchmark_results.csv")
