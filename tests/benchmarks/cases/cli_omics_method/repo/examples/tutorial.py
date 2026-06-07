matrix = read_csv("data/assay.csv")
scores = rank_features(matrix)
write("results/ranked_features.tsv", scores)
