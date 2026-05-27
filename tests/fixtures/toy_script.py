import csv

input_path = "data/demo_input.csv"
output_path = "results/summary.json"

with open(input_path, newline="") as handle:
    rows = list(csv.DictReader(handle))

print(len(rows), output_path)
