assay = read_csv("data/assay.tsv")
ranked = rank_features(assay)
write("results/report.tsv", ranked)
