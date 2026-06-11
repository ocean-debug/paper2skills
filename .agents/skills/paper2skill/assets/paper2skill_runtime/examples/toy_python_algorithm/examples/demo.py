from toy_algorithm import summarize

input_path = "data/demo_input.csv"
output_path = "results/summary.json"
summary_column = "value"

result = summarize(input_path)
print(result)
