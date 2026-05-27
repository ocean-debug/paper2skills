summarize_values <- function(path) {
  data <- read.csv(path)
  mean(data$value)
}
