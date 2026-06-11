library(stats)

input_path <- "data/demo_input.csv"
output_path <- "results/summary.csv"
data <- read.csv(input_path)
write.csv(summary(data$value), output_path)
