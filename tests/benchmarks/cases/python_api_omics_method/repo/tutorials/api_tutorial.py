from omics_api import summarize

counts = read_csv("data/raw_counts.csv")
norm_counts = normalize_counts(counts)
log_counts = log1p_transform(norm_counts)
write("results/score_table.tsv", log_counts)
summary = summarize("data/raw_counts.csv")
