import os

NAMESPACES = """@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix dcat:  <http://www.w3.org/ns/dcat#> .
@prefix dct:   <http://purl.org/dc/terms/> .
@prefix adms:  <http://www.w3.org/ns/adms#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix :      <http://example.org/ns#> . """

FORMATS = ["csv", "xls", "json", "ttl", "rdf", "txt", "xml"]
SIZES = [10, 100, 1000, 5000]

def generate_dataset(template_file, out_dir, count):
    with open(template_file, "r", encoding="utf-8") as f:
        template = f.read()

    base, ext = os.path.splitext(os.path.basename(template_file))
    out_file = os.path.join(out_dir, f"{base}_{count}{ext}")

    with open(out_file, "w", encoding="utf-8") as out:
        if ext in (".ttl", ".trig", ".n3", ".ttlstar"):
            out.write(NAMESPACES + "\n\n")

        for i in range(1, count + 1):
            instance = template
            instance = instance.replace("%%statement%%", f"stm{i}")
            instance = instance.replace("%%distribution%%", f"Dist{((i - 1) // 2) + 1}")
            instance = instance.replace("%%format%%", FORMATS[(i - 1) % len(FORMATS)])
            out.write(instance + "\n")

    print(f"{count} generated triplets to {out_file}")

if __name__ == "__main__":
    in_dir = "templates"
    out_dir = "datasets"
    os.makedirs(out_dir, exist_ok=True)

    for fname in os.listdir(in_dir):
        if fname.endswith((".ttl", ".trig", ".nq", ".n3", ".nt", ".ttlstar")):
            for size in SIZES:
                generate_dataset(os.path.join(in_dir, fname), out_dir, size)
