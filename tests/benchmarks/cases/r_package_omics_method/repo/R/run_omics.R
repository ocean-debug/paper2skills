run_omics <- function(input_file, output_file) {
  obj <- readRDS(input_file)
  obj <- normalizeOmics(obj)
  saveRDS(obj, output_file)
}
