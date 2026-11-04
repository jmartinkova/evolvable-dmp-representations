import csv

with open("runs.csv", newline="") as source:
    reader = csv.DictReader(source)

    with open("runs-measured.csv", "w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(
            row for row in reader
            if row["phase"] == "measurement"
        )