from pathlib import Path
import re

SIZES = [10, 100, 1000, 10000]
BASE_IRI = "https://example.org/benchmark/"
EXTENSIONS = {".ttl", ".trig", ".nq", ".n3", ".nt", ".ttlstar"}

PLACEHOLDER = re.compile(r"%%[^%\s]+%%")


def generate_dataset(template_file, header_file, out_dir, count):
    template = template_file.read_text(encoding="utf-8")
    header = header_file.read_text(encoding="utf-8")

    supported = {
        "%%dataset%%",
        "%%statement%%",
        "%%inclusion%%",
    }

    unknown = set(PLACEHOLDER.findall(template)) - supported
    if unknown:
        raise ValueError(
            f"{template_file}: neznámé placeholdery {sorted(unknown)}"
        )

    if PLACEHOLDER.search(header):
        raise ValueError(
            f"{header_file}: hlavička obsahuje placeholdery"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{template_file.stem}_{count}{template_file.suffix}"

    with out_file.open("w", encoding="utf-8") as out:
        out.write(header.rstrip() + "\n\n")

        for i in range(1, count + 1):
            values = {
                "%%dataset%%": f"{BASE_IRI}dataset/{i}",
                "%%statement%%": f"{BASE_IRI}statement/{i}",
                "%%inclusion%%": f"{BASE_IRI}inclusion/{i}",
            }

            instance = template
            for placeholder, value in values.items():
                instance = instance.replace(placeholder, value)

            out.write(instance.rstrip() + "\n\n")

    print(f"{count} Statements → {out_file}")


def main():
    templates_dir = Path("templates")
    headers_dir = Path("headers")
    out_dir = Path("datasets")

    templates = sorted(
        path for path in templates_dir.iterdir()
        if path.is_file() and path.suffix in EXTENSIONS
    )

    if not templates:
        raise ValueError("Ve složce templates nejsou žádné šablony.")

    for template_file in templates:
        header_file = headers_dir / template_file.name

        if not header_file.is_file():
            raise FileNotFoundError(f"Chybí hlavička: {header_file}")

        for count in SIZES:
            generate_dataset(
                template_file,
                header_file,
                out_dir,
                count,
            )


if __name__ == "__main__":
    main()