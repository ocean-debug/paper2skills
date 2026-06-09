countData = read_csv("counts.tsv")
sample_metadata = read_csv("metadata.tsv")
design = "~ condition"
fit = fit_bulk_model(countData, sample_metadata, design=design)
write("results/differential_features.tsv", fit)
